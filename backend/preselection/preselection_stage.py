import random

from enum import Enum, unique
from loguru import logger
from typing import Dict, List, Optional, Tuple, Union

from backend.preselection import ContextPreselector
from backend.preselection import FocusPreselector
from backend.util.mmirs_timer import MMIRSTimer
from config import conf


@unique
class MergeOp(str, Enum):
    UNION = 'union'
    INTERSECTION = 'intersection'


class PreselectionStage(object):
    __singleton = None

    def __new__(cls, *args, **kwargs):
        if cls.__singleton is None:
            logger.info('Instantiating PreselectionStage!')
            cls.__singleton = super(PreselectionStage, cls).__new__(cls)

            cls.__context_preselector = ContextPreselector()
            cls.__focus_preselector = FocusPreselector()

            cls._conf = conf.preselection

            cls.timer = MMIRSTimer()

        return cls.__singleton

    def __merge_relevant_images(self,
                                focus: Dict[str, float],
                                context: Dict[str, float],
                                max_num_relevant: int,
                                min_num_relevant: int = 500,  # TODO do we want this?! what is a good number?
                                merge_op: MergeOp = MergeOp.INTERSECTION) -> List[str]:
        self.timer.start_measurement('PSS::merge_relevant_images')
        logger.debug(f"Merging with {merge_op}")

        # FIXME - when using coco, there are some image ids where the leading 0s are missing
        #  these are not filtered out by the set operations! this happens later when the TeranIss is created but should
        #  be done before... albeit it has no effect. just for cleanliness!

        if merge_op == MergeOp.UNION:
            merged = list(focus.keys() | context.keys())
            logger.debug(f"Merge size: {len(merged)}")
        elif merge_op == MergeOp.INTERSECTION:
            # intersect the key sets
            merged = list(focus.keys() & context.keys())
            logger.debug(f"Merge size: {len(merged)}")

            # union as fallback if (way) too less items got returned
            if len(merged) < min_num_relevant:
                logger.debug(f"Too few merged images from intersection! Merging with UNION as fallback!")
                merged = list(focus.keys() | context.keys())
        else:
            raise NotImplementedError(f"Merge Operation {merge_op} not implemented!")

        if len(merged) > max_num_relevant:
            # shuffle the merged list because otherwise we would discard the docs with the lowest scores and since
            # focus relevant scores are wtf_idf scores and are larger than cosine sim scores, it would always discard
            # the focus similar docs.
            # TODO think of a way to include an equal number of context and focus relevant docs if possible.
            #  or discard context docs if more context docs are found (or vice versa for focus docs)
            #  - just take the top k//2 from context and focus !?
            random.shuffle(merged)
            return merged[:max_num_relevant]

        self.timer.stop_measurement()
        return merged

    def retrieve_top_k_context_relevant_images(self, context: str, dataset: str, k: int = 100, exact: bool = False):
        self.timer.start_measurement('PSS::retrieve_top_k_context_relevant_images')
        context_relevant = self.__context_preselector.retrieve_top_k_relevant_images(context,
                                                                                     k=k,
                                                                                     dataset=dataset,
                                                                                     exact=exact)
        self.timer.stop_measurement()
        return context_relevant

    def retrieve_top_k_focus_relevant_images(self,
                                             focus: str,
                                             dataset: str,
                                             k: int = 100,
                                             weight_by_sim: bool = False,
                                             top_k_similar: Optional[int] = None,
                                             max_similar: Optional[int] = None,
                                             return_similar_terms: Optional[bool] = False) -> \
            Union[Tuple[Dict[str, float], List[str]], Dict[str, float]]:
        self.timer.start_measurement('PSS::retrieve_top_k_focus_relevant_images')
        focus_relevant = self.__focus_preselector.retrieve_top_k_relevant_images(focus,
                                                                                 k=k,
                                                                                 dataset=dataset,
                                                                                 weight_by_sim=weight_by_sim,
                                                                                 top_k_similar=top_k_similar,
                                                                                 max_similar=max_similar,
                                                                                 return_similar_terms=return_similar_terms)
        self.timer.stop_measurement()

        return focus_relevant

    def retrieve_relevant_images(self,
                                 focus: str,
                                 context: str,
                                 dataset: str,
                                 merge_op: MergeOp = MergeOp.INTERSECTION,
                                 max_num_focus_relevant: int = 5000,
                                 max_num_context_relevant: int = 5000,
                                 max_num_relevant: int = 5000,
                                 min_num_relevant: int = 500,
                                 focus_weight_by_sim: bool = False,
                                 exact_context_retrieval: bool = False) -> List[str]:

        self.timer.start_measurement('PSS::retrieve_relevant_images')
        # TODO do this in two parallel threads!
        context_relevant = self.retrieve_top_k_context_relevant_images(context=context,
                                                                       dataset=dataset,
                                                                       k=max_num_context_relevant,
                                                                       exact=exact_context_retrieval)

        focus_relevant = self.retrieve_top_k_focus_relevant_images(focus=focus,
                                                                   dataset=dataset,
                                                                   k=max_num_focus_relevant,
                                                                   weight_by_sim=focus_weight_by_sim)

        merged = self.__merge_relevant_images(focus=focus_relevant,
                                              context=context_relevant,
                                              max_num_relevant=max_num_relevant,
                                              min_num_relevant=min_num_relevant,
                                              merge_op=merge_op)
        self.timer.stop_measurement()

        return merged
