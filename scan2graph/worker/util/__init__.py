"""
Util extractor module for SCAN2GRAPH.
"""
from .geometry import extract_mesh_from_shape
from .pcd_util import (
    read_point_cloud,
    # voxel_downsample,
    # remove_statistical_outliers,
    floor_removal,
    compact_point_cloud,
    extract_plane_groups,
    make_plane_colors,
    pick_seed_point,
    print_ifc_wall_options,
    RegistrationValidation,
    load_ifc_reference_cloud,
    preprocess_point_cloud,
    global_registration,
    refine_registration,
)
from .sdf_util import (
    safe_name,
    write_obj,
    pretty_xml,
)

__all__ = [
    'extract_mesh_from_shape',
    'read_point_cloud',
    # 'voxel_downsample',
    # 'remove_statistical_outliers',
    'floor_removal',
    'compact_point_cloud',
    'extract_plane_groups',
    'make_plane_colors',
    'pick_seed_point',
    'print_ifc_wall_options',
    'safe_name',
    'write_obj',
    'pretty_xml',
    'RegistrationValidation',
    'load_ifc_reference_cloud',
    'preprocess_point_cloud',
    'global_registration',
    'refine_registration',
]
