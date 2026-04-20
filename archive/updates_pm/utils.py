from __future__ import annotations
from typing import Any
import time
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# all custom indexes, used by drop/restore for explain comparisons
INDEX_REGISTRY: dict[str, list[dict[str, Any]]] = {
    "listings": [
        {"keys": [("address.market", 1), ("property_type", 1)], "name": "idx_market_proptype"},
        {"keys": [("amenities", 1)], "name": "idx_amenities"},
        {"keys": [("host.host_id", 1)], "name": "idx_host_id"},
        {"keys": [("host.host_is_superhost", 1), ("address.market", 1)], "name": "idx_superhost_market"},
        {"keys": [("address.market", 1), ("number_of_reviews", 1)], "name": "idx_market_nreviews"},
        {"keys": [("address.market", 1), ("price", 1)], "name": "idx_market_price"},
        {"keys": [("address.market", 1), ("review_scores.review_scores_rating", 1)], "name": "idx_market_rating"},
    ],
    "reviews": [
        {"keys": [("listing_id", 1), ("date", 1)], "name": "idx_listing_date"},
    ],
    "transactions": [
        {"keys": [("listing_id", 1)], "name": "idx_txn_listing"},
    ],
}


def register_index(collection: str, keys: list[tuple], name: str, **kwargs: Any) -> None:
    """Add an index to the registry for managed drop/restore."""
    if collection not in INDEX_REGISTRY:
        INDEX_REGISTRY[collection] = []
    existing = {idx["name"] for idx in INDEX_REGISTRY[collection]}
    if name not in existing:
        INDEX_REGISTRY[collection].append({"keys": keys, "name": name, **kwargs})


def drop_custom_indexes(database: Any) -> None:
    """Drop all custom indexes in the registry."""
    for coll, indexes in INDEX_REGISTRY.items():
        for idx in indexes:
            try:
                database[coll].drop_index(idx["name"])
            except Exception:
                pass


def restore_custom_indexes(database: Any) -> None:
    """Recreate all custom indexes from the registry."""
    for coll, indexes in INDEX_REGISTRY.items():
        for idx in indexes:
            opts = {k: v for k, v in idx.items() if k != "keys"}
            database[coll].create_index(idx["keys"], **opts)


def find_scan_stage(plan: dict[str, Any]) -> dict[str, Any]:
    """Walk inputStage chain to the leaf scan stage."""
    while "inputStage" in plan:
        plan = plan["inputStage"]
    return plan


def parse_agg_explain(expl: dict[str, Any]) -> dict[str, Any]:
    """Extract key metrics from an aggregation explain result."""
    m: dict[str, Any] = {}
    stages = expl.get("stages", [])
    if stages:
        cur = stages[0].get("$cursor", {})
        es = cur.get("executionStats", {})
        qp = cur.get("queryPlanner", {}).get("winningPlan", {})
        leaf = find_scan_stage(qp)
        m["Scan type"] = leaf.get("stage", "-")
        m["Index used"] = leaf.get("indexName", "none")
        m["Docs examined"] = es.get("totalDocsExamined", "-")
        m["Keys examined"] = es.get("totalKeysExamined", "-")
        m["Returned"] = es.get("nReturned", "-")
        m["Exec time (ms)"] = es.get("executionTimeMillis", "-")
    return m


def explain_compare(
    database: Any,
    collection: str,
    pipeline_before: list[dict[str, Any]],
    pipeline_after: list[dict[str, Any]],
    label_before: str = "Before (no indexes, naive)",
    label_after: str = "After (indexes + optimised)",
    extra_before: dict[str, Any] | None = None,
    extra_after: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Drop all custom indexes, explain + time pipeline_before,
    restore indexes, then explain + time pipeline_after.
    Returns a comparison DataFrame.
    """
    explain_fn = lambda p: database.command({
        "explain": {"aggregate": collection, "pipeline": p, "cursor": {}},
        "verbosity": "executionStats",
    })

    drop_custom_indexes(database)

    t0 = time.time()
    expl_b = explain_fn(pipeline_before)
    wall_b = round((time.time() - t0) * 1000, 1)
    t0 = time.time()
    list(database[collection].aggregate(pipeline_before))
    exec_b = round((time.time() - t0) * 1000, 1)

    restore_custom_indexes(database)

    t0 = time.time()
    expl_a = explain_fn(pipeline_after)
    wall_a = round((time.time() - t0) * 1000, 1)
    t0 = time.time()
    list(database[collection].aggregate(pipeline_after))
    exec_a = round((time.time() - t0) * 1000, 1)

    before_m = parse_agg_explain(expl_b)
    after_m = parse_agg_explain(expl_a)
    before_m["Pipeline exec (ms)"] = exec_b
    after_m["Pipeline exec (ms)"] = exec_a
    before_m["Wall time (ms)"] = wall_b
    after_m["Wall time (ms)"] = wall_a
    if extra_before:
        before_m.update(extra_before)
    if extra_after:
        after_m.update(extra_after)

    return pd.DataFrame({label_before: before_m, label_after: after_m})


def plot_boxplot(
    data: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    xlabel: str,
    ylabel: str,
    hue: str | None = None,
    order: list[str] | None = None,
    hue_order: list[str] | None = None,
    palette: str | dict = "Set2",
    figsize: tuple[int, int] = (14, 5),
    rotate_x: int = 0,
    legend_loc: str = "best",
) -> None:
    """Seaborn box plot with consistent styling."""
    fig, ax = plt.subplots(figsize=figsize)
    sns.boxplot(
        data=data, x=x, y=y, hue=hue,
        order=order, hue_order=hue_order,
        palette=palette, fliersize=2, linewidth=0.8, ax=ax,
    )
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if hue:
        ax.legend(title=hue.replace("_", " ").title(), loc=legend_loc)
    if rotate_x:
        ax.tick_params(axis="x", rotation=rotate_x)
    plt.tight_layout()
    plt.show()


def plot_lollipop(
    data: pd.DataFrame,
    x: str,
    y_cols: list[str],
    labels: list[str],
    title: str,
    xlabel: str,
    ylabel: str,
    colors: list[str] | None = None,
    figsize: tuple[int, int] = (14, 6),
    rotate_x: int = 30,
) -> None:
    """Double lollipop chart for side-by-side category comparison."""
    if colors is None:
        colors = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA"]
    fig, ax = plt.subplots(figsize=figsize)
    x_pos = range(len(data))
    for i, (col, label) in enumerate(zip(y_cols, labels)):
        offset = (i - len(y_cols) / 2 + 0.5) * 0.15
        positions = [p + offset for p in x_pos]
        ax.vlines(positions, 0, data[col], color=colors[i % len(colors)], linewidth=1.5)
        ax.scatter(positions, data[col], color=colors[i % len(colors)], s=50, zorder=3, label=label)
    ax.set_xticks(list(x_pos))
    ax.set_xticklabels(data[x], rotation=rotate_x, ha="right")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    plt.tight_layout()
    plt.show()


def plot_scatter(
    data: pd.DataFrame,
    x: str,
    y: str,
    size: str,
    color_col: str,
    title: str,
    xlabel: str,
    ylabel: str,
    palette: dict[str, str] | None = None,
    size_scale: float = 3.0,
    figsize: tuple[int, int] = (12, 6),
    xtick_labels: list[str] | None = None,
) -> None:
    """Scatter plot with size and color per category, jittered to avoid overlap."""
    fig, ax = plt.subplots(figsize=figsize)
    categories = data[color_col].unique().tolist()
    n_cats = len(categories)
    jitter_width = 0.25
    offsets = {cat: (i - (n_cats - 1) / 2) * jitter_width for i, cat in enumerate(categories)}
    for cat in categories:
        sub = data[data[color_col] == cat]
        c = palette[cat] if palette and cat in palette else None
        ax.scatter(
            sub[x] + offsets[cat], sub[y], s=sub[size] * size_scale,
            c=c, alpha=0.75, edgecolors="k", linewidth=0.5,
            label=cat, zorder=3,
        )
    if xtick_labels:
        ax.set_xticks(range(1, len(xtick_labels) + 1))
        ax.set_xticklabels(xtick_labels)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(title=color_col.replace("_", " ").title())
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.show()
