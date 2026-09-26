// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import android.view.Choreographer
import android.view.Surface
import android.view.SurfaceHolder
import android.view.SurfaceView
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import com.google.android.filament.Camera
import com.google.android.filament.Engine
import com.google.android.filament.EntityManager
import com.google.android.filament.Filament
import com.google.android.filament.IndexBuffer
import com.google.android.filament.Material
import com.google.android.filament.MaterialInstance
import com.google.android.filament.RenderableManager
import com.google.android.filament.Renderer
import com.google.android.filament.Scene
import com.google.android.filament.SwapChain
import com.google.android.filament.Texture
import com.google.android.filament.TextureSampler
import com.google.android.filament.VertexBuffer
import com.google.android.filament.View as FilamentView
import com.pathfindergod.spoke.ui.dice.Die
import com.pathfindergod.spoke.ui.dice.Impact
import com.pathfindergod.spoke.ui.theme.GodTypography
import com.pathfindergod.spoke.ui.theme.TextSecondary
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import java.nio.ShortBuffer
import kotlin.random.Random

private class PitRig {
    var engine: Engine? = null
    var renderer: Renderer? = null
    var scene: Scene? = null
    var view: FilamentView? = null
    var camera: Camera? = null
    var swapChain: SwapChain? = null
    var renderable = 0
    var vertexBuffer: VertexBuffer? = null
    var indexBuffer: IndexBuffer? = null
    var material: Material? = null
    var instance: MaterialInstance? = null
    var texture: Texture? = null
    var surface: Surface? = null
    var running = false
    var angleX = 0.6f
    var angleY = 0f
    var velX = 0f
    var velY = 0f
    var settleAt = 0L
    var impacted = true
    var currentDie: Die? = null
    var onImpact: () -> Unit = {}
    var lastNanos = 0L
    val frame = object : Choreographer.FrameCallback {
        override fun doFrame(now: Long) {
            if (!running) return
            Choreographer.getInstance().postFrameCallback(this)
            step(now)
        }
    }

    fun step(now: Long) {
        val dt = if (lastNanos == 0L) {
            0.016f
        } else {
            ((now - lastNanos) / 1_000_000_000.0).toFloat().coerceIn(0f, 0.1f)
        }
        lastNanos = now
        if (now >= settleAt && !impacted) {
            impacted = true
            onImpact()
        }
        val idle = 0.35f
        val pull = 1f - kotlin.math.exp(-dt * 2.0f)
        velX += (0f - velX) * pull
        velY += (idle - velY) * pull
        angleX += velX * dt
        angleY += velY * dt
        val engine = engine ?: return
        engine.getTransformManager().setTransform(renderable, rotYX(angleY, angleX))
        val renderer = renderer ?: return
        val swapChain = swapChain ?: return
        val view = view ?: return
        if (renderer.beginFrame(swapChain, now)) {
            renderer.render(view)
            renderer.endFrame()
        }
    }

    fun kick(dramatic: Boolean, fire: () -> Unit) {
        velY = if (dramatic) 14f else 9f
        velX = (Random.nextFloat() - 0.5f) * 6f
        settleAt = System.nanoTime() + (if (dramatic) 2_400_000_000L else 1_400_000_000L)
        impacted = false
        onImpact = fire
    }
}

private fun rotYX(ry: Float, rx: Float): FloatArray {
    val cy = kotlin.math.cos(ry)
    val sy = kotlin.math.sin(ry)
    val cx = kotlin.math.cos(rx)
    val sx = kotlin.math.sin(rx)
    val rotY = floatArrayOf(
        cy, 0f, -sy, 0f,
        0f, 1f, 0f, 0f,
        sy, 0f, cy, 0f,
        0f, 0f, 0f, 1f,
    )
    val rotX = floatArrayOf(
        1f, 0f, 0f, 0f,
        0f, cx, sx, 0f,
        0f, -sx, cx, 0f,
        0f, 0f, 0f, 1f,
    )
    val out = FloatArray(16)
    for (row in 0 until 4) {
        for (col in 0 until 4) {
            var sum = 0f
            for (k in 0 until 4) sum += rotY[row + k * 4] * rotX[k + col * 4]
            out[row + col * 4] = sum
        }
    }
    return out
}

@Composable
fun FilamentPit(
    die: Die,
    rollToken: Int,
    impact: Impact = Impact.NORMAL,
    modifier: Modifier = Modifier,
    onImpact: () -> Unit = {},
) {
    val context = LocalContext.current
    val rig = remember { PitRig() }
    var failed by remember { mutableStateOf(false) }
    Box(
        modifier = modifier.pointerInput(Unit) {
            detectDragGestures { _, drag ->
                rig.velY = (rig.velY + drag.x * 0.006f).coerceIn(-20f, 20f)
                rig.velX = (rig.velX + drag.y * 0.006f).coerceIn(-20f, 20f)
            }
        },
        contentAlignment = Alignment.Center,
    ) {
        AndroidView(
            factory = { ctx ->
                SurfaceView(ctx).also { view ->
                    view.holder.addCallback(object : SurfaceHolder.Callback {
                        override fun surfaceCreated(holder: SurfaceHolder) {
                            rig.surface = holder.surface
                            rig.attach()
                        }

                        override fun surfaceChanged(
                            holder: SurfaceHolder,
                            format: Int,
                            width: Int,
                            height: Int,
                        ) {
                            rig.resize(width, height)
                        }

                        override fun surfaceDestroyed(holder: SurfaceHolder) {
                            rig.detach()
                        }
                    })
                }
            },
            modifier = Modifier.fillMaxSize(),
        )
        if (failed) {
            Text(
                text = "Pit failed to ignite.",
                style = GodTypography.bodyMedium,
                color = TextSecondary,
            )
        }
    }
    LaunchedEffect(Unit) {
        try {
            rig.boot(context, die) { failed = true }
        } catch (_: Exception) {
            failed = true
        }
    }
    LaunchedEffect(die) {
        if (rig.engine != null && rig.currentDie != die) {
            try {
                rig.swapMesh(die)
            } catch (_: Exception) {
                failed = true
            }
        }
    }
    LaunchedEffect(rollToken) {
        if (rollToken == 0) return@LaunchedEffect
        rig.kick(impact != Impact.NORMAL, onImpact)
    }
    DisposableEffect(Unit) {
        onDispose { rig.destroy() }
    }
}

private fun PitRig.boot(context: android.content.Context, die: Die, fail: () -> Unit) {
    try {
        Filament.init()
    } catch (_: Exception) {
        fail()
        return
    }
    val materialBytes = PitMaterial.buildOrLoad(context) ?: run {
        fail()
        return
    }
    val engine = Engine.create()
    this.engine = engine
    val renderer = engine.createRenderer()
    this.renderer = renderer
    val scene = engine.createScene()
    this.scene = scene
    val view = engine.createView()
    this.view = view
    val entityManager = EntityManager.get()
    val cameraEntity = entityManager.create()
    val camera = engine.createCamera(cameraEntity)
    this.camera = camera
    view.scene = scene
    view.camera = camera
    val material = Material.Builder()
        .payload(ByteBuffer.wrap(materialBytes), materialBytes.size)
        .build(engine)
    this.material = material
    val instance = material.createInstance()
    this.instance = instance
    installMesh(DieMeshBuilder.build(die))
    currentDie = die
    attach()
}

private fun PitRig.installMesh(mesh: DieMesh) {
    val engine = engine ?: return
    val instance = instance ?: return
    val bitmap = DieTexture.build(mesh.faceNumbers, mesh.faceKinds)
    val positions = mesh.positions
    val uvs = mesh.uvs
    val interleaved = FloatBuffer.allocate(mesh.indices.size * 5)
    for (i in mesh.indices.indices) {
        interleaved.put(positions[i * 3])
        interleaved.put(positions[i * 3 + 1])
        interleaved.put(positions[i * 3 + 2])
        interleaved.put(uvs[i * 2])
        interleaved.put(uvs[i * 2 + 1])
    }
    interleaved.rewind()
    val vertexBuffer = VertexBuffer.Builder()
        .vertexCount(mesh.indices.size)
        .bufferCount(1)
        .attribute(
            VertexBuffer.VertexAttribute.POSITION,
            0,
            VertexBuffer.AttributeType.FLOAT3,
            0,
            20,
        )
        .attribute(
            VertexBuffer.VertexAttribute.UV0,
            0,
            VertexBuffer.AttributeType.FLOAT2,
            12,
            20,
        )
        .build(engine)
    this.vertexBuffer = vertexBuffer
    vertexBuffer.setBufferAt(engine, 0, interleaved)
    val indexData = ShortBuffer.allocate(mesh.indices.size)
    indexData.put(mesh.indices)
    indexData.rewind()
    val indexBuffer = IndexBuffer.Builder()
        .indexCount(mesh.indices.size)
        .bufferType(IndexBuffer.Builder.IndexType.USHORT)
        .build(engine)
    this.indexBuffer = indexBuffer
    indexBuffer.setBuffer(engine, indexData)
    val texture = Texture.Builder()
        .width(DieTexture.WIDTH)
        .height(DieTexture.HEIGHT)
        .levels(1)
        .format(Texture.InternalFormat.RGBA8)
        .sampler(Texture.Sampler.SAMPLER_2D)
        .build(engine)
    this.texture = texture
    texture.setImage(
        engine,
        0,
        Texture.PixelBufferDescriptor(
            DieTexture.toRgbaBuffer(bitmap),
            Texture.Format.RGBA,
            Texture.Type.UBYTE,
        ),
    )
    bitmap.recycle()
    instance.setParameter(
        "baseColorMap",
        texture,
        TextureSampler(
            TextureSampler.MinFilter.LINEAR,
            TextureSampler.MagFilter.LINEAR,
            TextureSampler.WrapMode.CLAMP_TO_EDGE,
        ),
    )
    renderable = EntityManager.get().create()
    RenderableManager.Builder(1)
        .geometry(0, RenderableManager.PrimitiveType.TRIANGLES, vertexBuffer, indexBuffer)
        .material(0, instance)
        .culling(false)
        .build(engine, renderable)
    scene?.addEntity(renderable)
}

private fun PitRig.swapMesh(die: Die) {
    val engine = engine ?: return
    scene?.removeEntity(renderable)
    engine.destroyEntity(renderable)
    vertexBuffer?.let { engine.destroyVertexBuffer(it) }
    vertexBuffer = null
    indexBuffer?.let { engine.destroyIndexBuffer(it) }
    indexBuffer = null
    texture?.let { engine.destroyTexture(it) }
    texture = null
    installMesh(DieMeshBuilder.build(die))
    currentDie = die
}

private fun PitRig.attach() {
    val engine = engine ?: return
    val surface = surface ?: return
    if (swapChain != null) return
    swapChain = engine.createSwapChain(surface)
    if (!running) {
        running = true
        lastNanos = 0L
        Choreographer.getInstance().postFrameCallback(frame)
    }
}

private fun PitRig.resize(width: Int, height: Int) {
    if (width == 0 || height == 0) return
    camera?.setProjection(45.0, width.toDouble() / height, 0.1, 100.0, Camera.Fov.VERTICAL)
    camera?.lookAt(0.0, 0.5, 4.4, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)
}

private fun PitRig.detach() {
    running = false
    val engine = engine ?: return
    swapChain?.let { engine.destroySwapChain(it) }
    swapChain = null
}

private fun PitRig.destroy() {
    running = false
    val engine = engine ?: return
    swapChain?.let { engine.destroySwapChain(it) }
    swapChain = null
    vertexBuffer?.let { engine.destroyVertexBuffer(it) }
    indexBuffer?.let { engine.destroyIndexBuffer(it) }
    material?.let { engine.destroyMaterial(it) }
    texture?.let { engine.destroyTexture(it) }
    view?.let { engine.destroyView(it) }
    scene?.let { engine.destroyScene(it) }
    renderer?.let { engine.destroyRenderer(it) }
    engine.destroy()
}
