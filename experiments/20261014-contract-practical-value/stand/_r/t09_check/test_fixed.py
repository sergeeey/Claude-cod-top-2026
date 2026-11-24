import sys
from decimal import Decimal

import pytest

sys.path.insert(0, r"<HOME>/AppData/Local/Temp/claude/D--Claude-cod-top-2026/29a715b1-3478-43c8-b908-635a18c4834e/scratchpad/practical/_r/t09_check/fixed")
import money as m  # noqa: E402

D = Decimal


# ---- happy paths: must PASS ----
def test_ok_parse_basic():
    assert m.parse_amount(" 1 234,50 ₽ ") == D("1234.50")
    assert m.parse_amount("-12.5") == D("-12.5")


def test_ok_format_basic():
    assert m.format_amount(D("1234.5")) == "1 234,50"
    assert m.format_amount(D("-1234.5")) == "-1 234,50"


def test_ok_round_basic():
    assert m.round_money(D("1.234")) == D("1.23")
    assert m.round_money(D("1.236")) == D("1.24")


def test_ok_discount_basic():
    assert m.discount_rate(D("500")) == D("0")
    assert m.discount_rate(D("5000")) == D("0.10")
    assert m.apply_discount(D("2000")) == D("1900.00")


# ---- decoys: must PASS ----
def test_decoy_negative_zero():
    assert m.format_amount(D("-0.001")) == "0,00"


def test_decoy_refund_no_discount():
    assert m.discount_rate(D("-6000")) == D("0")


def test_decoy_comma_decimal():
    assert m.parse_amount("12,345") == D("12.345")


# ---- planted: must FAIL ----
def test_P1_empty_input():
    with pytest.raises(ValueError):
        m.parse_amount("")


def test_P1b_whitespace_input():
    with pytest.raises(ValueError):
        m.parse_amount("   ")


def test_P2_nbsp():
    assert m.parse_amount("1\u00a0234,50") == D("1234.50")


def test_P2b_narrow_nbsp():
    assert m.parse_amount("1\u202f234\u202f567") == D("1234567")


def test_P3_negative_grouping():
    assert m.format_amount(D("-123456")) == "-123 456,00"


def test_P4_half_up():
    assert m.round_money(D("0.125")) == D("0.13")


def test_P4b_half_up_negative():
    assert m.round_money(D("-0.125")) == D("-0.13")


def test_P5_threshold_1000():
    assert m.discount_rate(D("1000")) == D("0.05")
    assert m.apply_discount(D("1000")) == D("950.00")


def test_P6_precision_large():
    assert m.apply_discount(D("10000000000000000.10")) == D("9000000000000000.09")


def test_P6b_precision_moderate():
    assert m.apply_discount(D("123456789.15")) == D("111111110.24")
