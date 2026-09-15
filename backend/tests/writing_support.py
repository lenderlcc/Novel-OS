from tests.core.workflow.test_planning_source_lifecycle import post


def plan(client, url, version=1, **extra):
    return post(
        client,
        url + "/plans",
        {
            "expected_version": version - 1,
            "objective": "Plan",
            "required_outcome": "Outcome",
            **extra,
        },
    )


def chapter(client, project, sequence):
    row = post(
        client, project + "/chapters", dict(sequence=sequence, title="Chapter " + str(sequence))
    )
    return project + "/chapters/" + row["id"]
