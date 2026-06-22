"""Group pairwise duplicate matches into duplicate sets."""

from __future__ import annotations

from collections import defaultdict

from video_duplicate_finder.models import DuplicateGroup, MatchResult, VideoRecord


def group_duplicates(
    records: list[VideoRecord],
    matches: list[MatchResult],
) -> list[DuplicateGroup]:
    """Convert duplicate pairs into connected duplicate groups."""

    if not matches:
        return []

    parent: dict[str, str] = {}
    records_by_path = {record.path: record for record in records}

    def find(path: str) -> str:
        parent.setdefault(path, path)
        while parent[path] != path:
            parent[path] = parent[parent[path]]
            path = parent[path]
        return path

    def union(left: str, right: str) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for match in matches:
        union(match.path_a, match.path_b)

    component_paths: dict[str, set[str]] = defaultdict(set)
    for path in parent:
        component_paths[find(path)].add(path)

    groups: list[DuplicateGroup] = []
    for index, paths in enumerate(
        sorted(component_paths.values(), key=lambda items: sorted(items)[0]),
        start=1,
    ):
        files = [records_by_path[path] for path in sorted(paths) if path in records_by_path]
        if len(files) < 2:
            continue

        group_matches = [
            match
            for match in matches
            if match.path_a in paths and match.path_b in paths
        ]
        similarity_score = (
            sum(match.similarity_score for match in group_matches) / len(group_matches)
            if group_matches
            else 0.0
        )
        recommended = recommend_file_to_keep(files)
        groups.append(
            DuplicateGroup(
                group_id=f"group-{index:03d}",
                similarity_score=similarity_score,
                recommended_keep=recommended.path,
                files=files,
                matches=group_matches,
            )
        )

    return groups


def recommend_file_to_keep(records: list[VideoRecord]) -> VideoRecord:
    """Choose the best copy to keep within a duplicate group."""

    if not records:
        raise ValueError("Cannot recommend a file from an empty duplicate group.")

    return max(records, key=_recommendation_key)


def _recommendation_key(record: VideoRecord) -> tuple[int, int, float, float]:
    metadata = record.metadata
    return (
        metadata.resolution_pixels,
        metadata.file_size,
        metadata.duration or 0.0,
        metadata.modified_time,
    )

