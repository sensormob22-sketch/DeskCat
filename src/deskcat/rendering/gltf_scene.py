"""Scene normalization for the pinned panda3d-gltf 1.3.0 importer.

The importer can discard an empty Character when a rig has no animations and
its mesh is a sibling root. An identity parent keeps mesh and joints together.
No animation is added, and the asset on disk is never modified.
"""
from gltf._converter import Converter
from gltf.parseutils import parse_gltf_file


def load_skinned_scene(path):
    document = parse_gltf_file(str(path))
    if len(document.get('skins', [])) != 1:
        raise ValueError('Prototype requires exactly one skin/skeleton')
    scene = document['scenes'][document.get('scene', 0)]
    roots = list(scene['nodes'])
    if len(roots) > 1:
        wrapper = len(document['nodes'])
        document['nodes'].append({'name': 'DeskCatSceneRoot', 'children': roots})
        scene['nodes'] = [wrapper]
    # Render only the selected scene; keep all node/accessor indices unchanged.
    document['scenes'] = [scene]
    document['scene'] = 0
    converter = Converter(str(path))
    converter.update(document)
    return converter.active_scene
