import pickle
import time
from pathlib import Path
from typing import Dict, Any

import faiss
import numpy as np
from loguru import logger
from omegaconf import OmegaConf
from sentence_transformers import SentenceTransformer, util


def verify_embedding_structure(emb_struct: Dict[str, Any]) -> bool:
    for key in ['corpus_ids', 'embeddings', 'type', 'model', 'dataset']:
        assert key in emb_struct.keys(), f"Cannot find key '{key}' in Sentence Embedding Structure!"
    return True


def load_sentence_embeddings(path: Path) -> Dict[str, Any]:
    assert path.exists(), f"Cannot read {path}!"
    logger.info(f"Loading Sentence Embedding Structure from {str(path)}")
    with open(str(path), "rb") as fIn:
        data = pickle.load(fIn)
        verify_embedding_structure(data)
        logger.info(f"Successfully loaded {data['type']} Sentence Embeddings for {data['model']}!")
        return data


class ContextPreselector(object):
    __singleton = None

    def __new__(cls, *args, **kwargs):
        if cls.__singleton is None:
            logger.info('Instantiating Context Preselector!')
            cls.__singleton = super(ContextPreselector, cls).__new__(cls)

            conf = OmegaConf.load('config.yaml').preselection.context

            # setup sentence transformers (sbert)
            cls.symmetric_model = conf.sbert.symmetric_model
            cls.asymmetric_model = conf.sbert.asymmetric_model
            cls.max_seq_len = conf.sbert.max_seq_len

            cls.symmetric_embeddings = {
                k: load_sentence_embeddings(v) for d in conf.sbert.symmetric_embeddings for k, v in d.items()
            }
            cls.asymmetric_embeddings = {
                k: load_sentence_embeddings(v) for d in conf.sbert.asymmetric_embeddings for k, v in d.items()
            }

            logger.info("Loading SentenceTransformer Models into Memory...")
            cls.sembedders = {'symm': SentenceTransformer(cls.symmetric_model),
                              'asym': SentenceTransformer(cls.asymmetric_model)}

            # setup faiss
            cls.faiss_nprobe = conf.faiss.nprobe
            logger.info("Loading FAISS Indices into Memory...")
            cls.symmetric_indices = {
                k: faiss.read_index(v) for d in conf.faiss.symmetric_indices for k, v in d.items()
            }
            cls.asymmetric_indices = {
                k: faiss.read_index(v) for d in conf.faiss.asymmetric_indices for k, v in d.items()
            }

        return cls.__singleton

    def find_top_k_matches(self, query: str, k: int = 10, exact: bool = False):
        start_time = time.time()
        # TODO for now we only use symmetric and wicsmmir
        embs = self.symmetric_embeddings['wicsmmir']['embeddings']
        corpus_ids = self.symmetric_embeddings['wicsmmir']['corpus_ids']
        index = self.symmetric_indices['wicsmmir']

        # compute query embedding
        query_embedding = self.sembedders['symm'].encode(query)

        # normalize vector to unit length, so that inner product is equal to cosine similarity
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        query_embedding = np.expand_dims(query_embedding, axis=0)
        if not exact:
            # Approximate Nearest Neighbor (ANN) on FAISS INV Index (Voronoi Cells)
            # returns a matrix with distances and corpus ids.
            distances, cids = index.search(query_embedding, k)

            # We extract corpus ids and scores for the first query
            hits = [{'corpus_id': cid, 'score': score} for cid, score in zip(cids[0], distances[0])]
        else:
            # Approximate Nearest Neighbor (ANN) is not exact, it might miss entries with high cosine similarity
            hits = util.semantic_search(query_embedding,
                                        embs,
                                        top_k=k)[0]

        hits = sorted(hits, key=lambda x: x['score'], reverse=True)
        top_k_matches = {corpus_ids[hit['corpus_id']]: hit['score'] for hit in hits[:k]}
        print(f"took: {time.time() - start_time}s")
        return top_k_matches
