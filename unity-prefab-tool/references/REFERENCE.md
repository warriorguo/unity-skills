# Unity YAML Prefab Format Reference

## File Structure

Unity 2022 prefab files use a multi-document YAML format:

```yaml
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &100000
GameObject:
  m_Name: MyObject
  m_Component:
  - component: {fileID: 100001}
  - component: {fileID: 100002}
--- !u!4 &100001
Transform:
  m_GameObject: {fileID: 100000}
  m_Father: {fileID: 0}
  m_Children:
  - {fileID: 100005}
  m_LocalPosition: {x: 0, y: 0, z: 0}
  m_LocalRotation: {x: 0, y: 0, z: 0, w: 1}
  m_LocalScale: {x: 1, y: 1, z: 1}
```

### Key Concepts

- **Document separator**: `--- !u!<classID> &<fileID>` marks each serialized object
- **classID**: Identifies the Unity type (e.g., 1 = GameObject, 4 = Transform)
- **fileID**: Unique identifier within this file for cross-referencing
- **Object references**: `{fileID: <number>}` for local references, `{fileID: <number>, guid: <hex>, type: 2/3}` for external asset references
- **`fileID: 0`** means null/none reference

### Hierarchy

The parent-child hierarchy is built through Transform components:
- `m_Father`: Reference to the parent Transform (fileID: 0 = root)
- `m_Children`: List of references to child Transforms
- Each Transform has `m_GameObject` pointing to its owning GameObject
- Each GameObject has `m_Component` listing its attached components

### Prefab Variants

Prefab Variants use `PrefabInstance` (classID 1001):

```yaml
--- !u!1001 &100100
PrefabInstance:
  m_SourcePrefab: {fileID: 100100000, guid: abc123..., type: 3}
  m_Modification:
    m_TransformParent: {fileID: 0}
    m_Modifications:
    - target: {fileID: 100000, guid: abc123..., type: 3}
      propertyPath: m_Name
      value: OverriddenName
```

Objects with ` stripped` suffix (e.g., `--- !u!1 &100000 stripped`) are references to objects in the source prefab that have modifications.

## ClassID Mapping Table

| ClassID | Type Name | Description |
|---------|-----------|-------------|
| 1 | GameObject | Base entity in the scene |
| 4 | Transform | Position, rotation, scale + hierarchy |
| 20 | Camera | Camera component |
| 21 | Material | Material asset |
| 23 | MeshRenderer | Renders a mesh with materials |
| 25 | Renderer | Base renderer class |
| 28 | Texture2D | 2D texture asset |
| 33 | MeshFilter | Holds a reference to a Mesh |
| 43 | Mesh | Mesh geometry data |
| 48 | Shader | Shader program |
| 54 | Rigidbody | Physics rigid body |
| 64 | MeshCollider | Mesh-based collision |
| 65 | BoxCollider | Box collision shape |
| 78 | AudioListener | Receives audio |
| 81 | AudioSource | Plays audio |
| 82 | AudioClip | Audio data asset |
| 83 | RenderTexture | Render target texture |
| 95 | Animator | Animation state machine |
| 96 | TrailRenderer | Renders trail effect |
| 102 | TextMesh | Legacy text rendering |
| 104 | RenderSettings | Scene render settings |
| 108 | Light | Light source |
| 111 | AnimationClip | Animation data |
| 114 | MonoBehaviour | Custom C# script component |
| 115 | MonoScript | Script asset reference |
| 120 | LineRenderer | Renders lines |
| 135 | SphereCollider | Sphere collision shape |
| 136 | CapsuleCollider | Capsule collision shape |
| 137 | SkinnedMeshRenderer | Animated mesh renderer |
| 143 | CharacterController | Character physics |
| 198 | Terrain | Terrain component |
| 205 | ParticleSystem | Particle effects |
| 206 | ParticleSystemRenderer | Renders particles |
| 208 | LODGroup | Level-of-detail switching |
| 212 | SpriteRenderer | 2D sprite rendering |
| 222 | CanvasRenderer | UI rendering component |
| 223 | Canvas | UI canvas root |
| 224 | RectTransform | UI transform (extends Transform) |
| 225 | CanvasGroup | UI group alpha/interactable |
| 236 | PlayableDirector | Timeline playback |
| 237 | VideoPlayer | Video playback |
| 248 | Grid | 2D grid (Tilemap) |
| 249 | Tilemap | Tile-based map |
| 250 | TilemapRenderer | Renders tilemap |
| 258 | SortingGroup | Sprite sorting |
| 290 | VisualEffect | VFX Graph effect |
| 1001 | PrefabInstance | Prefab instance/variant |

### Common Internal Fields

These fields appear on most serialized objects and are usually not interesting for inspection:

| Field | Description |
|-------|-------------|
| `m_ObjectHideFlags` | Editor visibility flags |
| `m_CorrespondingSourceObject` | Reference to source in prefab |
| `m_PrefabInstance` | Associated PrefabInstance |
| `m_PrefabAsset` | Associated Prefab asset |
| `m_GameObject` | Owning GameObject (on components) |
| `m_EditorHideFlags` | Editor-only hide flags |

### GameObject Key Fields

| Field | Description |
|-------|-------------|
| `m_Name` | Object name |
| `m_IsActive` | Whether the object is active |
| `m_Layer` | Physics/rendering layer (integer) |
| `m_TagString` | Tag string (e.g., "Untagged", "Player") |
| `m_Component` | List of attached components |

### Transform Key Fields

| Field | Description |
|-------|-------------|
| `m_LocalPosition` | Local position {x, y, z} |
| `m_LocalRotation` | Local rotation quaternion {x, y, z, w} |
| `m_LocalScale` | Local scale {x, y, z} |
| `m_Father` | Parent transform reference |
| `m_Children` | Child transform references |
| `m_RootOrder` | Sibling order index |

### MonoBehaviour Key Fields

| Field | Description |
|-------|-------------|
| `m_Script` | Reference to the MonoScript asset (contains GUID) |
| `m_Enabled` | Whether the script is enabled |
| Custom fields | All public/[SerializeField] fields from the C# class |
