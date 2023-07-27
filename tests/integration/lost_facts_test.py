from collections import Counter
import itertools
import os
from pathlib import Path
from sqlalchemy import create_engine

from ferc_xbrl_extractor.cli import get_instances, TAXONOMY_MAP
from ferc_xbrl_extractor.xbrl import extract, process_instance


def test_lost_fact_finder(tmp_path):
    instances = get_instances(
        Path(os.getenv("PUDL_INPUT"))
        / "ferc1"
        / "10.5281-zenodo.7314437"
        / "ferc1-xbrl-2021.zip"
    )

    used_ids = extract(
        instances=instances[:1],
        engine=create_engine("sqlite:///:memory:"),
        taxonomy=TAXONOMY_MAP[1],
        form_number=1,
        metadata_path=Path(tmp_path) / "metadata.json",
    )

    instance = instances[0].parse()
    instant_facts = itertools.chain.from_iterable(
        itertools.chain.from_iterable(
            context.values() for context in instance.instant_facts.values()
        )
    )
    duration_facts = itertools.chain.from_iterable(
        itertools.chain.from_iterable(
            context.values() for context in instance.duration_facts.values()
        )
    )
    all_facts = list(itertools.chain(instant_facts, duration_facts))

    def clean_fact(fact, contexts):
        return {"name": fact.name, "context": contexts[fact.c_id], "value": fact.value}

    lost_facts = [
        clean_fact(f, instance.contexts)
        for f in all_facts
        if f.f_id not in used_ids[instances[0].name]
    ]

    lostest_names = Counter(f["name"] for f in lost_facts)
    breakpoint()

    assert len(lost_facts) / len(all_facts) < 0.1
    # print(lost_facts_info)
    """
    date | entity | sorted_dims | fact_name | value
    ----------------
    2021-12-31 | AP | [("dim1", 1), ("dim2", 2)] | Why Don't I have a home? | 17 
    2021-12-31 | AP | [("dim1", 1)] | Why Don't I have a home? | 18 
    ....

    """

    # questions we could ask:

    # most common fact names
    # most common (fact name, {non-null dimensions})
