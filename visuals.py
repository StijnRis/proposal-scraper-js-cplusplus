import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt


def show_table_counts_for_project(db_path: str):
    # Get all tables
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    tables = [row[0] for row in cur.fetchall()]
    print(f"Tables in database {db_path}:")

    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  {table}: {count} rows")
    conn.close()


def plot_proposals_per_year(db_path: str, project_id: str, project_name: str, save_path: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Use SQLite to compute first revision year per proposal, then count per year.
    cur.execute(
        """
        SELECT year, COUNT(*) as proposals FROM (
            SELECT proposal_id, strftime('%Y', MIN(created_at)) AS year
            FROM ProposalRevision
            WHERE project_id = ?
            GROUP BY proposal_id
        )
        GROUP BY year
        ORDER BY year;
        """,
        (project_id,),
    )

    rows = cur.fetchall()
    conn.close()

    years = [int(r[0]) for r in rows if r[0] is not None]
    counts = [r[1] for r in rows if r[0] is not None]

    fig, ax = plt.subplots(figsize=(8, 4))
    if years:
        ax.bar(years, counts, color="#3b82f6")
        ax.set_xlabel("Year")
        ax.set_ylabel("Number of proposals")
        ax.set_title(f"Proposals per year — {project_name}")
        ax.set_xticks(years)
        ax.set_xticklabels([str(y) for y in years], rotation=45)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
    else:
        ax.text(0.5, 0.5, "No proposal revision dates found", ha="center", va="center")
        ax.set_axis_off()

    fig.tight_layout()

    fig.savefig(save_path)

if __name__ == "__main__":
    items = [
        {
            "db_path": "js/output/js_proposals.db",
            "project_id": 1,
            "project_name": "JavaScript",
            "save_path": "js/output/plots",
        },
        {
            "db_path": "cplusplus/output/cplusplus_proposals.sqlite3",
            "project_id": 1,
            "project_name": "C++",
            "save_path": "cplusplus/output/plots",
        },
    ]

    for item in items:
        print(
            f"Showing table counts for project {item['project_name']} (ID: {item['project_id']})"
        )

        # check if db_path exists
        if not Path(item["db_path"]).exists():
            raise RuntimeError(
                f"Database file {item['db_path']} does not exist. Run the main.py script first to create it."
            )
        # Make sure save_path directory exists
        Path(item["save_path"]).mkdir(parents=True, exist_ok=True)

        show_table_counts_for_project(
            db_path=item["db_path"]
        )

        plot_proposals_per_year(
            db_path=item["db_path"],
            project_name=item["project_name"],
            project_id=item["project_id"],
            save_path=item["save_path"] + "/proposals_per_year.png",
        )
