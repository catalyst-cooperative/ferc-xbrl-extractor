import itertools
import os
from collections import Counter
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from ferc_xbrl_extractor.cli import TAXONOMY_MAP, get_instances
from ferc_xbrl_extractor.xbrl import extract, get_fact_tables, process_instance


def test_lost_fact_finder(tmp_path):
    instances = get_instances(
        Path(os.getenv("PUDL_INPUT"))
        / "ferc1"
        / "10.5281-zenodo.7314437"
        / "ferc1-xbrl-2021.zip"
    )

    used_ids = extract(
        instances=instances,
        engine=create_engine("sqlite:///:memory:"),
        taxonomy=TAXONOMY_MAP[1],
        form_number=1,
        batch_size=50,
        metadata_path=Path(tmp_path) / "metadata.json",
    )
    tables = get_fact_tables(
        taxonomy_path=TAXONOMY_MAP[1],
        form_number=1,
        db_path="path",
        metadata_path=Path(tmp_path) / "metadata.json",
    )

    lost_facts = []

    def clean_fact(fact, contexts):
        return {
            "name": fact.name,
            "context": contexts[fact.c_id],
            "value": fact.value,
            "instant": contexts[fact.c_id].period.instant,
        }

    num_all_facts = 0
    for instance_builder in instances:
        if len(used_ids[instance_builder.name]) < 10:
            print(f"Skipping: {instance_builder.name}")
            continue

        instance = instance_builder.parse()
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
        num_all_facts += len(all_facts)

        lost_facts += [
            clean_fact(f, instance.contexts)
            for f in all_facts
            if f.f_id not in used_ids[instance_builder.name]
        ]

    lostest_names = Counter(f["name"] for f in lost_facts)

    rows = [
        {
            "name": fact["name"],
            "filing": instance_builder.name,
            "entity": fact["context"].entity.identifier,
            "start_date": fact["context"].period.start_date,
            "end_date": fact["context"].period.end_date,
            "dimensions": [
                (dim.name, dim.value) for dim in fact["context"].entity.dimensions
            ],
            "value": fact["value"],
            "table_candidates": [
                key
                for key, table in tables.items()
                if (fact["name"] in table.columns)
                and (fact["instant"] == table.instant)
            ],
            "period": "instant" if fact["instant"] else "duration",
        }
        for fact in lost_facts
    ]
    df = pd.DataFrame(rows)
    print(f"Of {num_all_facts} facts, {len(df) / num_all_facts}% were lost")
    df.drop(df[df["name"] == "OrderNumber"].index, inplace=True)
    df.to_pickle("lost_facts.pickle")
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
