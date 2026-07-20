"""Test XBRL taxonomy interface."""

import pytest

from ferc_xbrl_extractor.taxonomy import Concept, LinkRole


@pytest.mark.parametrize(
    "from_list,bad_list,exception_type,match",
    [
        (
            Concept.from_list,
            ["not_concept", {}, {}],
            ValueError,
            "First element should be 'concept'",
        ),
        (
            Concept.from_list,
            ["concept", "not_a_dict", {}],
            TypeError,
            "Second 2 elements should be dicts",
        ),
        (
            LinkRole.from_list,
            ["not_linkRole", {}],
            ValueError,
            "First element should be 'linkRole'",
        ),
        (
            LinkRole.from_list,
            ["linkRole", "not_a_dict"],
            TypeError,
            "Second element should be a dict",
        ),
    ],
    ids=[
        "concept-wrong-first-element",
        "concept-non-dict-elements",
        "link-role-wrong-first-element",
        "link-role-non-dict-second-element",
    ],
)
def test_from_list_rejects_malformed_arelle_input(
    from_list, bad_list, exception_type, match
):
    """Concept.from_list() and LinkRole.from_list() validate Arelle's list structure.

    Both expect Arelle to represent taxonomy structures as a list with a specific
    literal string in the first position and dicts in the next 1-2 positions.
    """
    with pytest.raises(exception_type, match=match):
        from_list(bad_list, concept_dict={})
