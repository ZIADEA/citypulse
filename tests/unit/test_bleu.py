"""test_bleu.py — Tests du score BLEU (module utils pur Python)"""
from app.utils.bleu import compute_bleu1

def test_bleu_identical():
    assert compute_bleu1("hello world logistics", "hello world logistics") > 0.9

def test_bleu_empty_hypothesis():
    assert compute_bleu1("reference text", "") == 0.0

def test_bleu_empty_reference():
    assert compute_bleu1("", "hypothesis") == 0.0

def test_bleu_partial_overlap():
    score = compute_bleu1("delivery vehicle route", "delivery truck road")
    assert 0.0 < score < 1.0

def test_bleu_no_overlap():
    assert compute_bleu1("alpha beta gamma", "delta epsilon zeta") == 0.0

def test_bleu_brevity_penalty():
    score = compute_bleu1("a b c d e f", "a")
    assert score < 0.5
