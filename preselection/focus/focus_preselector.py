import time
from typing import Dict

import numba
import numpy as np
import pandas as pd
from loguru import logger
from omegaconf import OmegaConf
from pymagnitude import Magnitude

from preselection.focus.visual_vocab import VisualVocab


@numba.jit
def weight(row):
    return row.wtf_idf * row.weight


class FocusPreselector(object):
    __singleton = None

    def __new__(cls, *args, **kwargs):
        if cls.__singleton is None:
            logger.info('Instantiating Focus Preselector!')
            cls.__singleton = super(FocusPreselector, cls).__new__(cls)

            cls.vocab = VisualVocab()
            conf = OmegaConf.load('config.yaml').preselection.focus

            # load magnitude
            cls.magnitude = Magnitude(conf.magnitude.embeddings)
            cls.top_k_similar = conf.magnitude.top_k_similar
            cls.max_similar = conf.magnitude.max_similar
            # perform warm up (first time takes about 20s)
            cls.get_top_k_similar_terms(cls.__singleton, "warmup")

            # load wtf-idf and set multi index
            cls.wtf_idf = pd.read_feather(conf.wtf_idf.index)
            mi = pd.MultiIndex.from_frame(cls.wtf_idf[['term', 'doc']])
            cls.wtf_idf = cls.wtf_idf[['wtf_idf']].set_index(mi)
            logger.info(f"Loaded WTF-IDF Index with {len(cls.wtf_idf)} entries!")

            # TODO use spacy for POS Tag, lemma, cleaning etc
            cls.max_focus_tokens = conf.max_focus_tokens
            cls.remove_puncts = conf.remove_puncts
            cls.remove_stopwords = conf.remove_stopwords

            cls.puncts = list('.:,;-_`%&+?!#()[]{}/\\\'"§')
            cls.stopwords = ['the', 'a']

        return cls.__singleton

    @logger.catch
    def get_top_k_similar_terms(self, focus: str) -> Dict[str, float]:
        # TODO use spacy for tokens, POS, lemma, cleaning etc
        focus_terms = focus.split(' ')
        # add the full focus term
        focus_terms.append(focus)

        # term -> similarity as weight
        # largest weight for the 'original' terms if the terms are in the vocab
        similar_terms = {ft: 1. for ft in focus_terms if ft in self.vocab}

        # compute the similarities between each focus term and all terms in the vocab
        # then keep the top-k and add the term-similarity pairs to the similar terms mapping
        for ft in focus_terms:
            sims = self.magnitude.similarity(ft, self.vocab.full_vocab)
            similar_terms.update({self.vocab[idx]: sim for idx, sim in zip(np.argsort(sims)[-self.top_k_similar:][::-1],
                                                                           sorted(sims)[-self.top_k_similar:][::-1])})
        # sort by similarity and keep only top-k
        similar_terms = {k: min(v, 1.) for k, v in
                         sorted(similar_terms.items(), key=lambda i: i[1], reverse=True)[:self.max_similar]}

        return similar_terms

    @logger.catch
    def retrieve_top_k_relevant_images(self, focus, k: int = 100, weight_by_sim: bool = False):
        start = time.time()
        similar_terms = self.get_top_k_similar_terms(focus)
        logger.debug(f"get_top_k_similar_terms took {time.time() - start}s")

        # remove terms which are not in the index
        start = time.time()
        # TODO this can be improved!
        similar_terms = {t: s for t, s in similar_terms.items() if t in self.wtf_idf.index}
        logger.debug(f"remove terms which are not in the index took {time.time() - start}s")

        # get the relevant entries (i.e. entries that match the similar terms)
        start = time.time()
        entries = self.wtf_idf.loc[similar_terms.keys()]
        logger.debug(f"get the relevant entries took {time.time() - start}s")

        if weight_by_sim:
            start = time.time()
            # TODO how to boost performance of creating the weights dict?!
            weights = np.array([similar_terms[t] for t, _ in entries.index])
            # create temporary weight dataframe
            # weights = pd.DataFrame(data=[*similar_terms.items()], columns=['term', 'weight']).set_index('term')

            # weight the wtf-idf scores by multiplying with the similarity of the term
            # entries = entries.assign(**weights).drop(columns=['weight'])
            entries['wtf_idf'] = entries['wtf_idf'].to_numpy() * weights
            # entries = entries.assign(**weights, wtf_idf=lambda x: x.wtf_idf * x.weight).drop(columns=['weight'])
            # entries = entries.assign(**weights, wtf_idf=weight).drop(columns=['weight'])
            logger.debug(f"weight_by_sim took {time.time() - start}s")

        # sum the wtf-idf scores and sort descending
        start = time.time()
        entries = entries.groupby('doc').sum()
        logger.debug(f"sum the wtf-idf scores took {time.time() - start}s")

        start = time.time()
        entries = entries.sort_values(by='wtf_idf', ascending=False)
        logger.debug(f"sort descending took {time.time() - start}s")

        return entries[:k]

    # naive implementation way to slow (86s for a three token focus word)
    # @logger.catch(reraise=True)
    # def retrieve_top_k_relevant_images(self, focus, k: int = 100):
    #     similar_terms = self.get_top_k_similar_terms(focus)
    #     doc_scores = {}
    #
    #     for term, sim in similar_terms.items():
    #         if term in self.wtf_idf.index:
    #             # get the relevant rows
    #             rows = self.wtf_idf.xs(term)
    #             for _, row in rows.iterrows():
    #                 # accumulate the scores for the respective documents
    #                 #   -> weight the wtf-idf scores by the term similarity
    #                 #   -> the more similar the term, the more relevant is the doc in which the term occurs
    #                 try:
    #                     doc_scores[row['doc']] += sim * row['wtf_idf']
    #                 except:
    #                     doc_scores[row['doc']] = sim * row['wtf_idf']
    #
    #     # return descending sorted docs
    #     return sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:k]
