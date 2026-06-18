"""
Regression tests for person-name and job-title validation.

Run with:  python test_validation.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import is_valid_person_name, is_valid_job_title, is_hr_role


# ── is_valid_person_name ─────────────────────────────────────────────────────

def test_name_rejects_marketing_heading():
    # Regression: this exact string caused a bad result
    assert not is_valid_person_name("Our People, Our Community"), \
        "'Our People, Our Community' must never be accepted as a person name"

def test_name_rejects_comma():
    assert not is_valid_person_name("Smith, John")

def test_name_rejects_single_word():
    assert not is_valid_person_name("Sarah")

def test_name_rejects_too_many_words():
    assert not is_valid_person_name("Chief Executive Officer Of Company")

def test_name_rejects_our_team():
    assert not is_valid_person_name("Our Team")

def test_name_rejects_the_company():
    assert not is_valid_person_name("The Company")

def test_name_rejects_sentence():
    assert not is_valid_person_name("See Some Amazing Stories")

def test_name_rejects_contains_people():
    assert not is_valid_person_name("Our People")

def test_name_rejects_contains_community():
    assert not is_valid_person_name("Local Community Leaders")

def test_name_accepts_full_name():
    assert is_valid_person_name("Sarah Johnson")

def test_name_accepts_three_words():
    assert is_valid_person_name("Mary Anne Smith")

def test_name_accepts_hyphenated():
    assert is_valid_person_name("Jean-Pierre Dubois")

def test_name_accepts_apostrophe():
    assert is_valid_person_name("Siobhan O'Brien")

def test_name_accepts_mc():
    assert is_valid_person_name("James McDonald")


# ── is_valid_job_title ───────────────────────────────────────────────────────

def test_title_rejects_sentence_with_period():
    assert not is_valid_job_title(
        "See some of the amazing stories of our people and communities around Australia."
    )

def test_title_rejects_our_people_phrase():
    assert not is_valid_job_title("See stories of our people and communities")

def test_title_rejects_too_long():
    assert not is_valid_job_title(
        "We are passionate about helping people achieve their goals every single day"
    )

def test_title_rejects_question():
    assert not is_valid_job_title("Want to join our team?")

def test_title_accepts_cpo():
    assert is_valid_job_title("Chief People Officer")

def test_title_accepts_head_of_people():
    assert is_valid_job_title("Head of People & Culture")

def test_title_accepts_hr_director():
    assert is_valid_job_title("HR Director")

def test_title_accepts_talent_acquisition():
    assert is_valid_job_title("Talent Acquisition Lead")

def test_title_accepts_l_and_d():
    assert is_valid_job_title("Learning and Development Manager")


# ── is_hr_role ───────────────────────────────────────────────────────────────

def test_hr_role_rejects_marketing_sentence():
    assert not is_hr_role(
        "See some of the amazing stories of our people and communities around Australia."
    )

def test_hr_role_rejects_our_people_body_copy():
    assert not is_hr_role("See stories of our people")

def test_hr_role_accepts_chief_people_officer():
    assert is_hr_role("Chief People Officer")

def test_hr_role_accepts_vp_people():
    assert is_hr_role("VP of People")

def test_hr_role_accepts_head_of_talent():
    assert is_hr_role("Head of Talent")

def test_hr_role_accepts_hr_business_partner():
    assert is_hr_role("HR Business Partner")

def test_hr_role_accepts_people_and_culture_manager():
    assert is_hr_role("People & Culture Manager")

def test_hr_role_accepts_dei_director():
    assert is_hr_role("Director of DEI")

def test_hr_role_rejects_people_person():
    assert not is_hr_role("people person")

def test_hr_role_rejects_customer_role():
    # "people" appears but it's not an HR title
    assert not is_hr_role("Serves people across Australia")


# ── runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
