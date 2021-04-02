import time

import pytest
from loguru import logger

from preselection.focus.focus_preselector import FocusPreselector


@pytest.fixture
def fps():
    return FocusPreselector()


def test_top_k_similar_terms_out_of_vocab(fps):
    f = "gyroscope"
    assert f not in fps.vocab

    similar = fps.get_top_k_similar_terms(f)

    assert type(similar) == dict
    assert len(similar) <= fps.max_similar
    assert len(similar) == fps.top_k_similar
    assert max(similar.values()) <= 1.0

    # test ordering
    sims = list(similar.values())
    for i in range(len(sims)):
        if i == 0:
            continue
        assert sims[i] <= sims[i - 1]


def test_top_k_similar_terms_single_focus(fps):
    similar = fps.get_top_k_similar_terms("building")
    assert type(similar) == dict
    assert len(similar) <= fps.max_similar
    assert max(similar.values()) <= 1.0

    # test ordering
    sims = list(similar.values())
    for i in range(len(sims)):
        if i == 0:
            continue
        assert sims[i] <= sims[i - 1]


def test_top_k_similar_terms_multiple_focus(fps):
    similar = fps.get_top_k_similar_terms("green building")
    assert type(similar) == dict
    assert len(similar) <= fps.max_similar
    assert max(similar.values()) <= 1.0

    # test ordering
    sims = list(similar.values())
    for i in range(len(sims)):
        if i == 0:
            continue
        assert sims[i] <= sims[i - 1]


def test_retrieve_top_k_relevant_images_out_of_vocab(fps):
    f = "gyroscope"
    assert f not in fps.vocab
    relevant = fps.retrieve_top_k_relevant_images(f)


def test_retrieve_top_k_relevant_images(fps):
    start = time.time()
    relevant = fps.retrieve_top_k_relevant_images("green building")
    logger.debug(f"First took {time.time() - start}s")

    start = time.time()
    relevant = fps.retrieve_top_k_relevant_images("green building")
    logger.debug(f"Second took {time.time() - start}s")

    start = time.time()
    relevant = fps.retrieve_top_k_relevant_images("green building")
    logger.debug(f"Third took {time.time() - start}s")