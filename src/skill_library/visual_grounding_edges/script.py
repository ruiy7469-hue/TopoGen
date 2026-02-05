import matplotlib.pyplot as plt
import networkx as nx
from src.language import t


def run(node_coords, adj_matrix):
    """
    Skill: GIR Visualization
    Renders the internal Graph-based Intermediate Representation for human-in-the-loop auditing.
    """
    fig, ax = plt.subplots(figsize=(7, 7))
    xs = [c[0] for c in node_coords]
    ys = [c[1] for c in node_coords]

    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    x_range = x_max - x_min if x_max != x_min else 100
    y_range = y_max - y_min if y_max != y_min else 100

    ax.set_xlim(x_min - 0.1 * x_range, x_max + 0.1 * x_range)
    ax.set_ylim(y_min - 0.1 * y_range, y_max + 0.1 * y_range)

    # Plot symbolic nodes
    for i, (x, y) in enumerate(node_coords):
        ax.plot(x, y, 'o', markersize=12, color='lightgray', zorder=1)
        ax.text(x, y, str(i), fontsize=10, color='black', ha='center', va='center', zorder=2)

    # Plot directed edges with offsets to prevent overlap
    n = len(node_coords)
    for i in range(n):
        for j in range(n):
            if i == j: continue
            if adj_matrix[i][j]:
                x1, y1 = node_coords[i]
                x2, y2 = node_coords[j]

                dx, dy = x2 - x1, y2 - y1
                length = (dx ** 2 + dy ** 2) ** 0.5
                if length == 0: continue

                off_x = -dy / length * 2.0
                off_y = dx / length * 2.0

                sx, sy = x1 + off_x, y1 + off_y
                ex, ey = x2 + off_x, y2 + off_y

                ax.annotate("", xy=(ex, ey), xytext=(sx, sy),
                            arrowprops=dict(arrowstyle="->", color="tab:blue", lw=1.5), zorder=5)

    ax.text(0.02, 0.98, t("plot_naming_ex"), transform=ax.transAxes,
            fontsize=10, color='blue', verticalalignment='top',
            bbox=dict(boxstyle="round", fc="white", alpha=0.8))

    ax.set_aspect('equal')
    ax.set_title(t("plot_net_preview"))
    ax.axis('off')
    plt.tight_layout()
    return fig
