// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.map

import com.pathfindergod.spoke.data.network.MapDoorDto
import com.pathfindergod.spoke.data.network.MapPropDto
import com.pathfindergod.spoke.data.network.MapSceneDto
import com.pathfindergod.spoke.data.network.MapTokenDto
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

enum class MapSurfaceKind {
    GROUND,
    FLOOR_STONE,
    FLOOR_VAULT,
    FLOOR_TAVERN,
    WALL,
    WOOD,
    STONE,
    METAL,
    FLAME,
    TOKEN_HERO,
    TOKEN_MONSTER,
    TOKEN_NPC,
    TOKEN_LOOT,
}

data class MapGeometryBatch(
    val kind: MapSurfaceKind,
    val positions: FloatArray,
    val normals: FloatArray,
    val uvs: FloatArray,
    val indices: IntArray,
) {
    val vertexCount: Int get() = positions.size / 3
}

data class MapGeometry(
    val batches: List<MapGeometryBatch>,
    val width: Int,
    val height: Int,
    val maxLevel: Int,
    val tileCount: Int,
    val propCount: Int,
    val radiusM: Float,
    val tileM: Float,
    val doorCount: Int = 0,
    val tokenCount: Int = 0,
)

object MapGeometryBuilder {

    const val LEVEL_M = 0.50f
    const val MAX_LEVEL = 8
    const val MAX_CELLS = 2_500
    const val MAX_PROPS = 8
    const val MAX_DOORS = 16
    const val MAX_TOKENS = 24

    private val PROP_TYPES = setOf("crate", "brazier", "pillar", "chest", "barrel", "altar")
    private val TOKEN_KINDS = setOf("hero", "monster", "npc", "loot")

    fun build(scene: MapSceneDto): MapGeometry {
        val width = scene.grid.w.coerceIn(1, 50)
        val height = scene.grid.h.coerceIn(1, 50)
        val tile = scene.grid.tileM
            .takeIf { it.isFinite() && it > 0f }
            ?.coerceIn(0.5f, 2f)
            ?: 1f
        require(width * height <= MAX_CELLS) { "map exceeds $MAX_CELLS cells" }

        val levels = IntArray(width * height)
        for (y in 0 until height) {
            val row = scene.heightmap.getOrNull(y) ?: continue
            for (x in 0 until width) {
                levels[y * width + x] = (row.getOrNull(x) ?: 0).coerceIn(0, MAX_LEVEL)
            }
        }
        for (corridor in scene.corridors) {
            for (cell in corridor.cells) {
                if (cell.size < 2) continue
                val cx = cell[0]
                val cy = cell[1]
                if (cx in 0 until width && cy in 0 until height && levels[cy * width + cx] == 0) {
                    levels[cy * width + cx] = 1
                }
            }
        }

        val meshes = LinkedHashMap<MapSurfaceKind, MeshBuilder>()
        fun mesh(kind: MapSurfaceKind): MeshBuilder = meshes.getOrPut(kind) { MeshBuilder(kind) }

        val halfX = width * tile / 2f
        val halfZ = height * tile / 2f
        mesh(MapSurfaceKind.GROUND).quad(
            -halfX - 1f, -0.02f, -halfZ - 1f,
            -halfX - 1f, -0.02f, halfZ + 1f,
            halfX + 1f, -0.02f, halfZ + 1f,
            halfX + 1f, -0.02f, -halfZ - 1f,
            0f, 1f, 0f,
        )

        var tileCount = 0
        var maxLevel = 0
        fun levelAt(x: Int, y: Int): Int =
            if (x in 0 until width && y in 0 until height) levels[y * width + x] else 0

        for (y in 0 until height) {
            for (x in 0 until width) {
                val level = levels[y * width + x]
                if (level <= 0) continue
                tileCount++
                maxLevel = maxOf(maxLevel, level)
                val x0 = (x - width / 2f) * tile
                val x1 = x0 + tile
                val z0 = (y - height / 2f) * tile
                val z1 = z0 + tile
                val topY = level * LEVEL_M
                val biome = biomeAt(scene, x, y)
                val topKind = if (level >= 3) {
                    MapSurfaceKind.WALL
                } else {
                    floorKind(biome)
                }
                mesh(topKind).quad(
                    x0, topY, z0,
                    x0, topY, z1,
                    x1, topY, z1,
                    x1, topY, z0,
                    0f, 1f, 0f,
                )
                val side = mesh(MapSurfaceKind.WALL)
                addSide(side, x0, z0, x1, z0, levelAt(x, y - 1), level, topY, 0f, 0f, -1f)
                addSide(side, x1, z1, x0, z1, levelAt(x, y + 1), level, topY, 0f, 0f, 1f)
                addSide(side, x0, z1, x0, z0, levelAt(x - 1, y), level, topY, -1f, 0f, 0f)
                addSide(side, x1, z0, x1, z1, levelAt(x + 1, y), level, topY, 1f, 0f, 0f)
            }
        }

        var propCount = 0
        for (prop in scene.props.take(MAX_PROPS)) {
            if (prop.type !in PROP_TYPES) continue
            if (prop.x !in 0 until width || prop.y !in 0 until height) continue
            propCount++
            val baseY = levelAt(prop.x, prop.y) * LEVEL_M
            val cx = (prop.x - width / 2f + 0.5f) * tile
            val cz = (prop.y - height / 2f + 0.5f) * tile
            addProp(::mesh, prop, cx, baseY, cz)
        }

        var doorCount = 0
        for (door in scene.doors.take(MAX_DOORS)) {
            if (door.x !in 0 until width || door.y !in 0 until height) continue
            doorCount++
            val lvl = levelAt(door.x, door.y)
            val baseY = (if (lvl in 1..2) lvl else 1) * LEVEL_M
            val cx = (door.x - width / 2f + 0.5f) * tile
            val cz = (door.y - height / 2f + 0.5f) * tile
            addDoor(::mesh, door, cx, baseY, cz)
        }

        var tokenCount = 0
        for (token in scene.tokens.take(MAX_TOKENS)) {
            val kindKey = token.kind.lowercase()
            if (kindKey !in TOKEN_KINDS) continue
            if (token.x !in 0 until width || token.y !in 0 until height) continue
            tokenCount++
            val lvl = levelAt(token.x, token.y)
            val baseY = maxOf(1, lvl) * LEVEL_M
            val cx = (token.x - width / 2f + 0.5f) * tile
            val cz = (token.y - height / 2f + 0.5f) * tile
            addToken(::mesh, token, kindKey, cx, baseY, cz)
        }

        val batches = meshes.values
            .mapNotNull { it.toBatch() }
            .sortedBy { it.kind.ordinal }
        return MapGeometry(
            batches = batches,
            width = width,
            height = height,
            maxLevel = maxLevel,
            tileCount = tileCount,
            propCount = propCount,
            radiusM = sqrt(halfX * halfX + halfZ * halfZ) + tile,
            tileM = tile,
            doorCount = doorCount,
            tokenCount = tokenCount,
        )
    }

    private fun floorKind(biome: String): MapSurfaceKind = when (biome.lowercase()) {
        "vault" -> MapSurfaceKind.FLOOR_VAULT
        "tavern" -> MapSurfaceKind.FLOOR_TAVERN
        else -> MapSurfaceKind.FLOOR_STONE
    }

    private fun biomeAt(scene: MapSceneDto, x: Int, y: Int): String {
        for (zone in scene.zones) {
            if (zone.rect.size != 4) continue
            val zx = zone.rect[0]
            val zy = zone.rect[1]
            val zw = zone.rect[2]
            val zh = zone.rect[3]
            if (x >= zx && x < zx + zw && y >= zy && y < zy + zh) return zone.biome
        }
        return "stone"
    }

    private fun addSide(
        mesh: MeshBuilder,
        ax: Float,
        az: Float,
        bx: Float,
        bz: Float,
        neighbourLevel: Int,
        level: Int,
        topY: Float,
        nx: Float,
        ny: Float,
        nz: Float,
    ) {
        if (neighbourLevel >= level) return
        val low = neighbourLevel * LEVEL_M
        mesh.quad(
            ax, low, az,
            bx, low, bz,
            bx, topY, bz,
            ax, topY, az,
            nx, ny, nz,
        )
    }

    private fun addProp(
        mesh: (MapSurfaceKind) -> MeshBuilder,
        prop: MapPropDto,
        cx: Float,
        baseY: Float,
        cz: Float,
    ) {
        val scale = prop.scale.takeIf { it.isFinite() }?.coerceIn(0.5f, 2f) ?: 1f
        val yaw = Math.toRadians(prop.rot.toDouble()).toFloat()
        when (prop.type) {
            "crate" -> mesh(MapSurfaceKind.WOOD).box(
                cx, baseY + 0.28f * scale, cz,
                0.28f * scale, 0.28f * scale, 0.28f * scale,
                yaw,
            )
            "barrel" -> mesh(MapSurfaceKind.WOOD).cylinder(
                cx, baseY, cz,
                0.26f * scale, 0.62f * scale, 10, yaw,
            )
            "pillar" -> {
                mesh(MapSurfaceKind.STONE).cylinder(
                    cx, baseY, cz,
                    0.22f * scale, 1.5f * scale, 10, yaw,
                )
                mesh(MapSurfaceKind.STONE).box(
                    cx, baseY + 0.05f * scale, cz,
                    0.32f * scale, 0.05f * scale, 0.32f * scale,
                    yaw,
                )
            }
            "chest" -> {
                mesh(MapSurfaceKind.WOOD).box(
                    cx, baseY + 0.16f * scale, cz,
                    0.26f * scale, 0.16f * scale, 0.18f * scale,
                    yaw,
                )
                mesh(MapSurfaceKind.METAL).box(
                    cx, baseY + 0.36f * scale, cz,
                    0.27f * scale, 0.06f * scale, 0.19f * scale,
                    yaw,
                )
            }
            "altar" -> {
                mesh(MapSurfaceKind.STONE).box(
                    cx, baseY + 0.24f * scale, cz,
                    0.45f * scale, 0.24f * scale, 0.30f * scale,
                    yaw,
                )
                mesh(MapSurfaceKind.STONE).box(
                    cx, baseY + 0.53f * scale, cz,
                    0.52f * scale, 0.05f * scale, 0.36f * scale,
                    yaw,
                )
            }
            "brazier" -> {
                mesh(MapSurfaceKind.METAL).cylinder(
                    cx, baseY, cz,
                    0.24f * scale, 0.55f * scale, 8, yaw,
                )
                mesh(MapSurfaceKind.FLAME).cylinder(
                    cx, baseY + 0.55f * scale, cz,
                    0.18f * scale, 0.30f * scale, 8, yaw,
                    topRadius = 0.02f,
                )
            }
        }
    }

    private fun addDoor(
        mesh: (MapSurfaceKind) -> MeshBuilder,
        door: MapDoorDto,
        cx: Float,
        baseY: Float,
        cz: Float,
    ) {
        val yaw = if (door.orientation.equals("ns", ignoreCase = true)) {
            0f
        } else {
            (PI / 2.0).toFloat()
        }
        val leafKind = if (door.kind.equals("secret", ignoreCase = true)) {
            MapSurfaceKind.STONE
        } else {
            MapSurfaceKind.WOOD
        }
        mesh(MapSurfaceKind.STONE).box(
            cx, baseY + 0.92f, cz,
            0.40f, 0.08f, 0.12f,
            yaw,
        )
        mesh(leafKind).box(
            cx, baseY + 0.42f, cz,
            0.34f, 0.42f, 0.07f,
            yaw,
        )
        mesh(MapSurfaceKind.METAL).box(
            cx, baseY + 0.42f, cz,
            0.06f, 0.06f, 0.09f,
            yaw,
        )
    }

    private fun addToken(
        mesh: (MapSurfaceKind) -> MeshBuilder,
        token: MapTokenDto,
        kindKey: String,
        cx: Float,
        baseY: Float,
        cz: Float,
    ) {
        val yaw = ((token.x * 31 + token.y * 17) and 3) * (PI.toFloat() / 2f)
        val surfaceKind = when (kindKey) {
            "hero" -> MapSurfaceKind.TOKEN_HERO
            "monster" -> MapSurfaceKind.TOKEN_MONSTER
            "npc" -> MapSurfaceKind.TOKEN_NPC
            else -> MapSurfaceKind.TOKEN_LOOT
        }
        mesh(MapSurfaceKind.METAL).cylinder(
            cx, baseY, cz,
            0.28f, 0.06f, 12, yaw,
        )
        when (kindKey) {
            "hero" -> {
                mesh(surfaceKind).cylinder(
                    cx, baseY + 0.06f, cz,
                    0.20f, 0.62f, 12, yaw,
                    topRadius = 0.14f,
                )
                mesh(surfaceKind).box(
                    cx, baseY + 0.78f, cz,
                    0.14f, 0.12f, 0.14f,
                    yaw,
                )
            }
            "monster" -> {
                mesh(surfaceKind).cylinder(
                    cx, baseY + 0.06f, cz,
                    0.24f, 0.58f, 10, yaw,
                    topRadius = 0.18f,
                )
                mesh(surfaceKind).cylinder(
                    cx, baseY + 0.64f, cz,
                    0.18f, 0.28f, 8, yaw,
                    topRadius = 0.01f,
                )
            }
            "npc" -> {
                mesh(surfaceKind).cylinder(
                    cx, baseY + 0.06f, cz,
                    0.18f, 0.56f, 12, yaw,
                    topRadius = 0.12f,
                )
                mesh(surfaceKind).cylinder(
                    cx, baseY + 0.62f, cz,
                    0.11f, 0.18f, 10, yaw,
                )
            }
            else -> {
                mesh(surfaceKind).box(
                    cx, baseY + 0.20f, cz,
                    0.20f, 0.14f, 0.16f,
                    yaw,
                )
                mesh(surfaceKind).cylinder(
                    cx, baseY + 0.34f, cz,
                    0.14f, 0.24f, 6, yaw,
                    topRadius = 0.01f,
                )
            }
        }
    }
}

private class FloatSink(initial: Int = 4_096) {
    private var data = FloatArray(initial)
    var size = 0
        private set

    fun add(value: Float) {
        if (size == data.size) data = data.copyOf(size * 2)
        data[size++] = value
    }

    fun toArray(): FloatArray = data.copyOf(size)
}

private class IntSink(initial: Int = 4_096) {
    private var data = IntArray(initial)
    var size = 0
        private set

    fun add(value: Int) {
        if (size == data.size) data = data.copyOf(size * 2)
        data[size++] = value
    }

    fun toArray(): IntArray = data.copyOf(size)
}

private class MeshBuilder(val kind: MapSurfaceKind) {
    private val positions = FloatSink()
    private val normals = FloatSink()
    private val uvs = FloatSink()
    private val indices = IntSink()

    private val vertexCount: Int get() = positions.size / 3

    fun quad(
        ax: Float, ay: Float, az: Float,
        bx: Float, by: Float, bz: Float,
        cx: Float, cy: Float, cz: Float,
        dx: Float, dy: Float, dz: Float,
        nx: Float, ny: Float, nz: Float,
    ) {
        val base = vertexCount
        vertex(ax, ay, az, nx, ny, nz, 0f, 0f)
        vertex(bx, by, bz, nx, ny, nz, 1f, 0f)
        vertex(cx, cy, cz, nx, ny, nz, 1f, 1f)
        vertex(dx, dy, dz, nx, ny, nz, 0f, 1f)
        indices.add(base)
        indices.add(base + 1)
        indices.add(base + 2)
        indices.add(base)
        indices.add(base + 2)
        indices.add(base + 3)
    }

    fun triangle(
        ax: Float, ay: Float, az: Float,
        bx: Float, by: Float, bz: Float,
        cx: Float, cy: Float, cz: Float,
        nx: Float, ny: Float, nz: Float,
    ) {
        val base = vertexCount
        vertex(ax, ay, az, nx, ny, nz, 0f, 0f)
        vertex(bx, by, bz, nx, ny, nz, 1f, 0f)
        vertex(cx, cy, cz, nx, ny, nz, 0.5f, 1f)
        indices.add(base)
        indices.add(base + 1)
        indices.add(base + 2)
    }

    fun box(
        cx: Float, cy: Float, cz: Float,
        hx: Float, hy: Float, hz: Float,
        yaw: Float,
    ) {
        val c = cos(yaw)
        val s = sin(yaw)
        fun px(x: Float, z: Float): Float = cx + x * c - z * s
        fun pz(x: Float, z: Float): Float = cz + x * s + z * c
        val x0 = -hx
        val x1 = hx
        val y0 = cy - hy
        val y1 = cy + hy
        val z0 = -hz
        val z1 = hz
        quad(px(x0, z1), y1, pz(x0, z1), px(x1, z1), y1, pz(x1, z1), px(x1, z0), y1, pz(x1, z0), px(x0, z0), y1, pz(x0, z0), 0f, 1f, 0f)
        quad(px(x0, z0), y0, pz(x0, z0), px(x1, z0), y0, pz(x1, z0), px(x1, z1), y0, pz(x1, z1), px(x0, z1), y0, pz(x0, z1), 0f, -1f, 0f)
        quad(px(x1, z1), y0, pz(x1, z1), px(x1, z1), y1, pz(x1, z1), px(x1, z0), y1, pz(x1, z0), px(x1, z0), y0, pz(x1, z0), c, 0f, s)
        quad(px(x0, z0), y0, pz(x0, z0), px(x0, z0), y1, pz(x0, z0), px(x0, z1), y1, pz(x0, z1), px(x0, z1), y0, pz(x0, z1), -c, 0f, -s)
        quad(px(x0, z1), y0, pz(x0, z1), px(x1, z1), y0, pz(x1, z1), px(x1, z1), y1, pz(x1, z1), px(x0, z1), y1, pz(x0, z1), s, 0f, c)
        quad(px(x1, z0), y0, pz(x1, z0), px(x0, z0), y0, pz(x0, z0), px(x0, z0), y1, pz(x0, z0), px(x1, z0), y1, pz(x1, z0), -s, 0f, -c)
    }

    fun cylinder(
        cx: Float, baseY: Float, cz: Float,
        radius: Float, height: Float,
        segments: Int,
        yaw: Float,
        topRadius: Float = radius,
    ) {
        val c = cos(yaw)
        val s = sin(yaw)
        val topY = baseY + height
        fun px(angle: Float, r: Float): Float {
            val lx = r * cos(angle)
            val lz = r * sin(angle)
            return cx + lx * c - lz * s
        }
        fun pz(angle: Float, r: Float): Float {
            val lx = r * cos(angle)
            val lz = r * sin(angle)
            return cz + lx * s + lz * c
        }
        fun nx(angle: Float): Float {
            val raw = cos(angle)
            return raw * c - sin(angle) * s
        }
        fun nz(angle: Float): Float {
            val raw = sin(angle)
            return raw * s + cos(angle) * c
        }
        val count = segments.coerceIn(3, 24)
        for (i in 0 until count) {
            val a0 = 2f * PI.toFloat() * i / count
            val a1 = 2f * PI.toFloat() * (i + 1) / count
            val normalX = nx((a0 + a1) / 2f)
            val normalZ = nz((a0 + a1) / 2f)
            if (topRadius <= 0.02f) {
                triangle(
                    px(a0, radius), baseY, pz(a0, radius),
                    px(a1, radius), baseY, pz(a1, radius),
                    cx, topY, cz,
                    normalX, 0f, normalZ,
                )
            } else {
                quad(
                    px(a0, radius), baseY, pz(a0, radius),
                    px(a1, radius), baseY, pz(a1, radius),
                    px(a1, topRadius), topY, pz(a1, topRadius),
                    px(a0, topRadius), topY, pz(a0, topRadius),
                    normalX, 0f, normalZ,
                )
            }
        }
        if (topRadius > 0.02f) {
            for (i in 0 until count) {
                val a0 = 2f * PI.toFloat() * i / count
                val a1 = 2f * PI.toFloat() * (i + 1) / count
                triangle(
                    cx, topY, cz,
                    px(a0, topRadius), topY, pz(a0, topRadius),
                    px(a1, topRadius), topY, pz(a1, topRadius),
                    0f, 1f, 0f,
                )
            }
        }
        for (i in 0 until count) {
            val a0 = 2f * PI.toFloat() * i / count
            val a1 = 2f * PI.toFloat() * (i + 1) / count
            triangle(
                cx, baseY, cz,
                px(a1, radius), baseY, pz(a1, radius),
                px(a0, radius), baseY, pz(a0, radius),
                0f, -1f, 0f,
            )
        }
    }

    private fun vertex(
        x: Float, y: Float, z: Float,
        nx: Float, ny: Float, nz: Float,
        u: Float, v: Float,
    ) {
        positions.add(x)
        positions.add(y)
        positions.add(z)
        normals.add(nx)
        normals.add(ny)
        normals.add(nz)
        uvs.add(u)
        uvs.add(v)
    }

    fun toBatch(): MapGeometryBatch? {
        if (indices.size == 0) return null
        return MapGeometryBatch(
            kind = kind,
            positions = positions.toArray(),
            normals = normals.toArray(),
            uvs = uvs.toArray(),
            indices = indices.toArray(),
        )
    }
}
