"""
Regression tests for person-name, role-title, and HR-role validation.

Run with:  python test_validation.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import (
    is_valid_person_name,
    is_valid_people_role_title,
    is_hr_role,
    source_quote_supports_person_and_role,
)


# ── is_valid_person_name ─────────────────────────────────────────────────────

# Regression: original bad results that must never pass
def test_name_rejects_our_people_our_community():
    assert not is_valid_person_name("Our People, Our Community")

def test_name_rejects_explore_expertise():
    assert not is_valid_person_name("Explore Expertise")

def test_name_rejects_about_us():
    assert not is_valid_person_name("About Us")

def test_name_rejects_people_development():
    assert not is_valid_person_name("People Development")

def test_name_rejects_leadership_team():
    assert not is_valid_person_name("Leadership Team")

def test_name_rejects_meet_the_team():
    assert not is_valid_person_name("Meet the Team")

def test_name_rejects_our_people():
    assert not is_valid_person_name("Our People")

def test_name_rejects_careers():
    assert not is_valid_person_name("Careers")

def test_name_rejects_contact_us():
    assert not is_valid_person_name("Contact Us")

# Structural rejects
def test_name_rejects_comma():
    assert not is_valid_person_name("Smith, John")

def test_name_rejects_single_word():
    assert not is_valid_person_name("Sarah")

def test_name_rejects_five_words():
    assert not is_valid_person_name("Chief Executive Officer Of Company")

def test_name_rejects_sentence_verb():
    assert not is_valid_person_name("Partnering To Create Progress")

def test_name_rejects_investing_phrase():
    assert not is_valid_person_name("Investing In Our People")

def test_name_rejects_community():
    assert not is_valid_person_name("Local Community Leaders")

def test_name_rejects_board():
    assert not is_valid_person_name("Board Directors")

def test_name_rejects_executive_team():
    assert not is_valid_person_name("Executive Team")

# Valid names
def test_name_accepts_two_word():
    assert is_valid_person_name("Sarah Johnson")

def test_name_accepts_three_word():
    assert is_valid_person_name("Mary Anne Smith")

def test_name_accepts_three_part_name():
    assert is_valid_person_name("Michael James Jones")

def test_name_accepts_hyphenated():
    assert is_valid_person_name("Jean-Paul Martin")

def test_name_accepts_apostrophe():
    assert is_valid_person_name("Siobhan O'Brien")

def test_name_accepts_mc():
    assert is_valid_person_name("James McDonald")

def test_name_accepts_van():
    # "Van" is not in the reject list — common surname prefix
    assert is_valid_person_name("Lisa Van Dyke")


# ── is_valid_people_role_title ───────────────────────────────────────────────

# Regression: original bad role titles that must never pass
def test_title_rejects_our_people():
    assert not is_valid_people_role_title("Our People")

def test_title_rejects_partnering_sentence():
    assert not is_valid_people_role_title(
        "Partnering to create progress through six pillars of excellence"
    )

def test_title_rejects_investing_sentence():
    assert not is_valid_people_role_title(
        "We believe that investing in our people, is investing in our future"
    )

def test_title_rejects_amazing_stories():
    assert not is_valid_people_role_title(
        "See some of the amazing stories of our people and communities around Australia."
    )

def test_title_rejects_explore_expertise():
    assert not is_valid_people_role_title("Explore Expertise")

def test_title_rejects_about_us():
    assert not is_valid_people_role_title("About Us")

# Structural rejects
def test_title_rejects_sentence_period():
    assert not is_valid_people_role_title("We invest in our people every day.")

def test_title_rejects_question():
    assert not is_valid_people_role_title("Want to join our team?")

def test_title_rejects_too_long():
    assert not is_valid_people_role_title(
        "We are passionate about helping our talented people achieve their goals"
    )

def test_title_rejects_no_seniority_word():
    # "people" alone without a seniority/function context must not pass
    assert not is_valid_people_role_title("People")

def test_title_rejects_our_prefix():
    assert not is_valid_people_role_title("Our Culture Team")

# Valid role titles (must all pass)
def test_title_accepts_cpo():
    assert is_valid_people_role_title("Chief People Officer")

def test_title_accepts_head_of_people():
    assert is_valid_people_role_title("Head of People")

def test_title_accepts_head_of_people_and_culture():
    assert is_valid_people_role_title("Head of People & Culture")

def test_title_accepts_hr_director():
    assert is_valid_people_role_title("HR Director")

def test_title_accepts_director_of_people():
    assert is_valid_people_role_title("Director of People & Culture")

def test_title_accepts_vp_hr():
    assert is_valid_people_role_title("VP Human Resources")

def test_title_accepts_talent_acquisition_manager():
    assert is_valid_people_role_title("Talent Acquisition Manager")

def test_title_accepts_people_development_manager():
    assert is_valid_people_role_title("People Development Manager")

def test_title_accepts_l_and_d():
    assert is_valid_people_role_title("Learning and Development Manager")

def test_title_accepts_hr_business_partner():
    assert is_valid_people_role_title("HR Business Partner")

def test_title_accepts_dei_director():
    assert is_valid_people_role_title("Director of DEI")

def test_title_accepts_employee_experience_lead():
    assert is_valid_people_role_title("Employee Experience Lead")

def test_title_accepts_talent_coordinator():
    assert is_valid_people_role_title("Talent Coordinator")

def test_title_accepts_chro():
    assert is_valid_people_role_title("CHRO")

def test_title_accepts_people_and_culture_manager():
    assert is_valid_people_role_title("People & Culture Manager")

def test_title_accepts_people_ops():
    assert is_valid_people_role_title("People Operations Manager")


# ── is_hr_role ───────────────────────────────────────────────────────────────

def test_hr_rejects_marketing_sentence():
    assert not is_hr_role(
        "Partnering to create progress through six pillars of excellence"
    )

def test_hr_rejects_our_people_body_copy():
    assert not is_hr_role("Our People")

def test_hr_rejects_explore_expertise():
    assert not is_hr_role("Explore Expertise")

def test_hr_rejects_people_person():
    assert not is_hr_role("people person")

def test_hr_accepts_chief_people_officer():
    assert is_hr_role("Chief People Officer")

def test_hr_accepts_vp_people():
    assert is_hr_role("VP of People")

def test_hr_accepts_head_of_talent():
    assert is_hr_role("Head of Talent")

def test_hr_accepts_hr_business_partner():
    assert is_hr_role("HR Business Partner")

def test_hr_accepts_people_and_culture_manager():
    assert is_hr_role("People & Culture Manager")

def test_hr_accepts_dei_director():
    assert is_hr_role("Director of DEI")

def test_hr_accepts_learning_and_development():
    assert is_hr_role("Learning and Development Manager")


# ── source_quote_supports_person_and_role ────────────────────────────────────

def test_quote_passes_when_empty():
    assert source_quote_supports_person_and_role("", "Jane Smith", "HR Director")

def test_quote_passes_when_name_and_role_present():
    assert source_quote_supports_person_and_role(
        "Jane Smith is our HR Director based in Sydney",
        "Jane Smith", "HR Director"
    )

def test_quote_fails_when_long_and_neither_name_nor_role():
    assert not source_quote_supports_person_and_role(
        "We partner with clients across six pillars of excellence globally",
        "Jane Smith", "HR Director"
    )

def test_quote_passes_when_short():
    # Short quotes (≤30 chars) can't be verified, so we don't reject them
    assert source_quote_supports_person_and_role(
        "Explore our team", "Jane Smith", "HR Director"
    )


# ── runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
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
