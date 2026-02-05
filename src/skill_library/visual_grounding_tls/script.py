import matplotlib.pyplot as plt
import networkx as nx
from src.language import t

def run(node_coords, adj_matrix, tls_nodes=None):
    """
    Skill: Signalized Layout Visualization
    Highlights identified Traffic Light System (TLS) nodes for spatial auditing.
    """
    fig, ax = plt.subplots(figsize=(7, 7))

    for i, (x, y) in enumerate(node_coords):
        color = 'lightgray'
        marker = 'o'
        size = 8
        label_color = 'gray'

        # Highlight nodes identified as signalized junctions (Degree >= 3)
        if tls_nodes and str(i) in tls_nodes:
            color = 'red'
            marker = 's'
            size = 12
            label_color = 'darkred'

        ax.plot(x, y, marker=marker, markersize=size, color=color, zorder=1)
        ax.text(x, y, str(i), fontsize=9, color=label_color, ha='center', va='center', zorder=2, fontweight='bold')

    # Draw topological edges
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

    ax.set_aspect('equal')
    ax.set_title(t("plot_net_tls"))
    ax.axis('off')
    return fig