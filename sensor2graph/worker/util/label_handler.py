"""
Interactive point cloud labeling and CSV management.
"""

from pathlib import Path

import open3d as o3d
import numpy as np
import pandas as pd


class InteractiveLabeler:
    """Interactive labeler for manual point cloud segmentation using Open3D."""

    def __init__(self, cloud_path, output_csv_path=None):
        """
        Initialize labeler with a point cloud.

        Args:
            cloud_path: Path to .pcd file.
            output_csv_path: Path to save labels CSV. If None, derives from cloud_path.
        """
        self.cloud_path = Path(cloud_path)
        self.cloud = o3d.io.read_point_cloud(str(self.cloud_path))
        self.points = np.asarray(self.cloud.points)
        self.n_points = len(self.points)

        if output_csv_path is None:
            self.csv_path = self.cloud_path.with_name(
                f"{self.cloud_path.stem}_labels.csv"
            )
        else:
            self.csv_path = Path(output_csv_path)

        # Initialize label arrays
        self.point_indices = np.arange(self.n_points)
        self.segment_ids = np.full(self.n_points, -1, dtype=np.int32)
        self.surface_types = np.full(self.n_points, "unlabeled", dtype=object)

        # Color array for visualization
        self.colors = np.ones((self.n_points, 3)) * 0.5  # Default gray

        # Color map for surface types
        self.color_map = {
            "floor": np.array([0.8, 0.6, 0.2]),  # tan
            "ceiling": np.array([0.7, 0.7, 0.9]),  # light blue
            "wall": np.array([0.7, 0.7, 0.7]),  # light gray
            "opening": np.array([1.0, 1.0, 0.0]),  # yellow
            "other": np.array([0.5, 0.5, 0.5]),  # dark gray
            "unlabeled": np.array([0.5, 0.5, 0.5]),  # dark gray
        }

        self.picked_indices = []

        print(f"\n{'='*60}")
        print(f"Interactive Labeler Initialized")
        print(f"{'='*60}")
        print(f"Cloud: {self.cloud_path}")
        print(f"Points: {self.n_points}")
        print(f"Output CSV: {self.csv_path}")
        print(f"\nSelection workflow:")
        print(f"  [Shift + Left] Pick points in Open3D")
        print(f"  [Ctrl + Left] Remove picked points")
        print(f"  [Q] Close viewer after picking")
        print(f"  [Then type the label in terminal]")
        print(f"  [1] Label as 'floor'")
        print(f"  [2] Label as 'ceiling'")
        print(f"  [3] Label as 'wall'")
        print(f"  [4] Label as 'opening'")
        print(f"  [5] Label as 'other'")
        print(f"  [S] Save labels to CSV")
        print(f"  [Q] Quit")
        print(f"{'='*60}\n")

    def pick_points(self):
        """Launch selection-capable Open3D viewer and return picked indices."""
        self.update_cloud_colors()
        visualizer = o3d.visualization.VisualizerWithEditing()
        visualizer.create_window(window_name="PCD Segmenter")
        visualizer.add_geometry(self.cloud)
        visualizer.run()
        picked = visualizer.get_picked_points()
        visualizer.destroy_window()
        self.picked_indices = list(picked)
        return self.picked_indices

    def assign_label(self, surface_type, segment_id=None):
        """
        Assign a label to currently selected points.

        Args:
            surface_type: One of 'floor', 'ceiling', 'wall', 'opening', 'other'.
            segment_id: Optional explicit segment ID; defaults to auto-increment.
        """
        if len(self.picked_indices) == 0:
            print("No points selected. Use box select first.")
            return

        if surface_type not in self.color_map:
            print(f"Unknown surface type: {surface_type}")
            return

        # Auto-increment segment ID if not specified
        if segment_id is None:
            current_segments = self.segment_ids[self.segment_ids >= 0]
            segment_id = int(current_segments.max()) + \
                1 if len(current_segments) > 0 else 0

        # Apply label
        for idx in self.picked_indices:
            self.segment_ids[idx] = segment_id
            self.surface_types[idx] = surface_type
            self.colors[idx] = self.color_map[surface_type]

        print(f"Labeled {len(self.picked_indices)} points as '{surface_type}' "
              f"(segment {segment_id})")
        self.picked_indices = []
        self.update_cloud_colors()

    def manual_label_by_range(self, ranges_dict):
        """
        Label points by coordinate ranges without GUI.

        Args:
            ranges_dict: Dict mapping surface_type to coordinate constraints.
            Example:
                {
                    'floor': {'z_max': 0.2},
                    'ceiling': {'z_min': 2.5},
                    'wall': {'x_min': 0, 'x_max': 5, 'z_min': 0.2, 'z_max': 2.5}
                }
        """
        segment_id = 0
        for surface_type, constraints in ranges_dict.items():
            mask = np.ones(self.n_points, dtype=bool)

            if 'x_min' in constraints:
                mask &= self.points[:, 0] >= constraints['x_min']
            if 'x_max' in constraints:
                mask &= self.points[:, 0] <= constraints['x_max']

            if 'y_min' in constraints:
                mask &= self.points[:, 1] >= constraints['y_min']
            if 'y_max' in constraints:
                mask &= self.points[:, 1] <= constraints['y_max']

            if 'z_min' in constraints:
                mask &= self.points[:, 2] >= constraints['z_min']
            if 'z_max' in constraints:
                mask &= self.points[:, 2] <= constraints['z_max']

            indices = np.where(mask)[0]
            if len(indices) > 0:
                self.segment_ids[indices] = segment_id
                self.surface_types[indices] = surface_type
                self.colors[indices] = self.color_map[surface_type]
                print(f"Labeled {len(indices)} points as '{surface_type}'")
                segment_id += 1

        self.update_cloud_colors()

    def update_cloud_colors(self):
        """Update point cloud colors based on current labels."""
        self.cloud.colors = o3d.utility.Vector3dVector(self.colors)

    def visualize(self):
        """Launch Open3D interactive viewer for manual selection."""
        return self.pick_points()

    def get_label_counts(self):
        """Return counts of labeled vs unlabeled points."""
        labeled_mask = self.segment_ids >= 0
        labeled_count = np.sum(labeled_mask)
        unlabeled_count = self.n_points - labeled_count

        print(f"\nLabel Summary:")
        print(f"  Labeled: {labeled_count} / {self.n_points}")
        print(f"  Unlabeled: {unlabeled_count} / {self.n_points}")
        print(f"\nBreakdown by surface type:")
        for surface_type in np.unique(self.surface_types):
            if surface_type != "unlabeled":
                count = np.sum(self.surface_types == surface_type)
                unique_segments = len(
                    np.unique(self.segment_ids[self.surface_types == surface_type]))
                print(
                    f"  {surface_type}: {count} points ({unique_segments} segments)")

    def save_labels_to_csv(self):
        """Save labels to CSV file."""
        df = pd.DataFrame({
            'point_index': self.point_indices,
            'segment_id': self.segment_ids,
            'surface_type': self.surface_types
        })
        df.to_csv(self.csv_path, index=False)
        print(f"\nLabels saved to: {self.csv_path}")
        return self.csv_path


def load_labels_from_csv(csv_path):
    """Load labels from CSV file."""
    df = pd.read_csv(csv_path)
    return df


def create_labeled_cloud(cloud_path, labels_df, output_pcd_path=None):
    """Create colored point cloud from labels."""
    cloud = o3d.io.read_point_cloud(str(cloud_path))
    points = np.asarray(cloud.points)

    color_map = {
        "floor": np.array([0.8, 0.6, 0.2]),
        "ceiling": np.array([0.7, 0.7, 0.9]),
        "wall": np.array([0.7, 0.7, 0.7]),
        "opening": np.array([1.0, 1.0, 0.0]),
        "other": np.array([0.5, 0.5, 0.5]),
        "unlabeled": np.array([0.5, 0.5, 0.5]),
    }

    colors = np.ones((len(points), 3)) * 0.5
    for idx, row in labels_df.iterrows():
        surface_type = row['surface_type']
        colors[idx] = color_map.get(surface_type, np.array([0.5, 0.5, 0.5]))

    cloud.colors = o3d.utility.Vector3dVector(colors)

    if output_pcd_path:
        o3d.io.write_point_cloud(str(output_pcd_path), cloud)
        print(f"Colored cloud saved: {output_pcd_path}")

    return cloud
