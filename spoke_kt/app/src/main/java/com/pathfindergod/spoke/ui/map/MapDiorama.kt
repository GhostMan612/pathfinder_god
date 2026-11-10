// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.map

import android.graphics.PixelFormat
import android.os.Handler
import android.os.Looper
import android.view.Choreographer
import android.view.Surface
import android.view.SurfaceHolder
import android.view.SurfaceView
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CenterFocusStrong
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.google.android.filament.Box as FilamentBox
import com.google.android.filament.Camera
import com.google.android.filament.ColorGrading
import com.google.android.filament.Engine
import com.google.android.filament.EntityManager
import com.google.android.filament.Filament
import com.google.android.filament.IndexBuffer
import com.google.android.filament.IndirectLight
import com.google.android.filament.LightManager
import com.google.android.filament.Material
import com.google.android.filament.RenderableManager
import com.google.android.filament.Renderer
import com.google.android.filament.Scene
import com.google.android.filament.SwapChain
import com.google.android.filament.SwapChainFlags
import com.google.android.filament.VertexBuffer
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.data.network.MapSceneDto
import com.pathfindergod.spoke.ui.designsystem.GodStatusText
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.designsystem.godTouchSize
import com.pathfindergod.spoke.ui.theme.GoldAccent
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.sin
import java.nio.FloatBuffer
import java.nio.IntBuffer
import com.google.android.filament.View as FilamentView

private const val MSAA_SAMPLES = 4
private const val ATTACH_RETRY_MS = 250L
private const val VERTEX_STRIDE = 36
private const val SH_BAND_COUNT = 3
// Filament's SH API takes bandCount² float3 coefficients, i.e. 3 bands = 9 * 3 floats.
private const val SH_COEFFICIENTS = 27
private const val SH_DC_SCALE = 1.772454f
private const val SH_Y_SCALE = -1.023390f
private const val SH_DC_FLOOR = 0.5f
private const val SH_Y_FLOOR = 1f / 3f

private class DioramaBuffers(
    val vertex: VertexBuffer,
    val index: IndexBuffer,
)

@Composable
fun MapDiorama(
    scene: MapSceneDto,
    prompt: String,
    modifier: Modifier = Modifier,
    onFailed: () -> Unit = {},
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val geometry = remember(scene) { MapGeometryBuilder.build(scene) }
    val rig = remember(geometry, scene) { DioramaRig(scene, geometry) }
    var ready by remember { mutableStateOf(false) }
    var failed by remember { mutableStateOf(false) }
    val resetLabel = stringResource(R.string.a11y_map_3d_reset)
    val description = stringResource(R.string.map_3d_description, prompt)
    val stateBuilding = stringResource(R.string.a11y_map_3d_state_building)
    val stateReady = stringResource(R.string.a11y_map_3d_state_ready)
    val stateFailed = stringResource(R.string.a11y_map_3d_state_failed)

    Box(
        modifier = modifier
            .pointerInput(geometry) {
                detectTransformGestures { _, pan, zoom, _ ->
                    rig.orbit(pan.x, pan.y, zoom)
                }
            }
            .semantics {
                contentDescription = description
                stateDescription = when {
                    failed -> stateFailed
                    ready -> stateReady
                    else -> stateBuilding
                }
                customActions = listOf(
                    CustomAccessibilityAction(resetLabel) {
                        rig.reset()
                        true
                    },
                )
            },
        contentAlignment = Alignment.Center,
    ) {
        key(rig) {
            AndroidView(
                factory = { ctx ->
                    SurfaceView(ctx).also { view ->
                        view.holder.setFormat(PixelFormat.RGBA_8888)
                        view.holder.addCallback(object : SurfaceHolder.Callback {
                            override fun surfaceCreated(holder: SurfaceHolder) {
                                rig.surface = holder.surface
                                rig.ensureLoop()
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
                                rig.detachSurface()
                            }
                        })
                    }
                },
                modifier = Modifier.fillMaxSize(),
            )
        }
        if (!ready && !failed) {
            GodStatusText(text = stringResource(R.string.map_3d_building))
        }
        if (failed) {
            GodStatusText(text = stringResource(R.string.map_3d_failed))
        }
        Icon(
            imageVector = Icons.Filled.CenterFocusStrong,
            contentDescription = resetLabel,
            tint = GoldAccent,
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(Spacing.sm)
                .clickable(
                    onClickLabel = resetLabel,
                    role = Role.Button,
                ) { rig.reset() }
                .testTag(GodTags.MAP_DIORAMA_RESET)
                .godTouchSize()
                .padding(Spacing.xs),
        )
    }

    LaunchedEffect(rig) {
        ready = false
        failed = false
        val payload = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.Default) {
            MapDioramaMaterial.prepare(context)
        }
        if (payload == null) {
            failed = true
            return@LaunchedEffect
        }
        kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.Main.immediate) {
            runCatching { rig.install(payload) }
        }
            .onSuccess { ready = true }
            .onFailure {
                android.util.Log.e("MapDiorama", "install failed", it)
                failed = true
            }
    }
    LaunchedEffect(failed) {
        if (failed) onFailed()
    }
    DisposableEffect(lifecycleOwner, rig) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> rig.ensureLoop()
                Lifecycle.Event.ON_STOP -> rig.pause()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            rig.destroy()
        }
    }
}

private class DioramaRig(
    private val sceneData: MapSceneDto,
    private val geometry: MapGeometry,
) {
    var surface: Surface? = null
    private var engine: Engine? = null
    private var renderer: Renderer? = null
    private var filamentScene: Scene? = null
    private var view: FilamentView? = null
    private var camera: Camera? = null
    private var swapChain: SwapChain? = null
    private var indirectLight: IndirectLight? = null
    private var colorGrading: ColorGrading? = null
    private var keyLight = 0
    private var cameraEntity = 0
    private var material: Material? = null
    private var running = false
    private var destroyed = false
    private var attachPending = false
    private var attachRetryAt = 0L
    private var viewportWidth = 1
    private var viewportHeight = 1
    private var msaaActive = false
    private val renderables = ArrayList<Int>()
    private val buffers = ArrayList<DioramaBuffers>()
    private val instances = ArrayList<com.google.android.filament.MaterialInstance>()
    private val pointLights = ArrayList<Int>()
    private val mainHandler = Handler(Looper.getMainLooper())

    private val focusY = geometry.maxLevel * MapGeometryBuilder.LEVEL_M * 0.4f
    private val defaultDistance = geometry.radiusM * 1.55f + 2.2f
    private val minDistance = geometry.radiusM * 0.65f + 1f
    private val maxDistance = geometry.radiusM * 3.2f + 6f
    private var yaw = 0.62f
    private var pitch = 0.62f
    private var distance = defaultDistance

    private val frame = object : Choreographer.FrameCallback {
        override fun doFrame(now: Long) {
            if (!running) return
            Choreographer.getInstance().postFrameCallback(this)
            step(now)
        }
    }

    fun orbit(panX: Float, panY: Float, zoom: Float) {
        yaw -= panX * 0.006f
        pitch = (pitch - panY * 0.006f).coerceIn(0.12f, 1.38f)
        if (zoom > 0.0001f) {
            distance = (distance / zoom).coerceIn(minDistance, maxDistance)
        }
    }

    fun reset() {
        yaw = 0.62f
        pitch = 0.62f
        distance = defaultDistance
    }

    fun resize(width: Int, height: Int) {
        if (width <= 0 || height <= 0) return
        viewportWidth = width
        viewportHeight = height
    }

    fun ensureLoop() {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            mainHandler.post { ensureLoop() }
            return
        }
        if (running || destroyed) return
        running = true
        Choreographer.getInstance().postFrameCallback(frame)
    }

    fun pause() {
        if (!running) return
        running = false
        Choreographer.getInstance().removeFrameCallback(frame)
    }

    fun detachSurface() {
        surface = null
        attachRetryAt = 0L
        val activeEngine = engine
        swapChain?.let { runCatching { activeEngine?.destroySwapChain(it) } }
        swapChain = null
        activeEngine?.flushAndWait()
    }

    private fun step(now: Long) {
        if (swapChain == null) {
            attach(now)
            if (swapChain == null) return
        }
        project()
        val activeRenderer = renderer ?: return
        val activeSwapChain = swapChain ?: return
        val activeView = view ?: return
        if (activeRenderer.beginFrame(activeSwapChain, now)) {
            activeRenderer.render(activeView)
            activeRenderer.endFrame()
        }
    }

    private fun attach(now: Long) {
        if (swapChain != null) {
            attachPending = false
            return
        }
        val activeEngine = engine ?: return
        val activeSurface = surface ?: return
        if (!activeSurface.isValid) return
        if (attachPending && now < attachRetryAt) return
        attachRetryAt = now + ATTACH_RETRY_MS * 1_000_000L
        msaaActive = supportedMsaa(activeEngine)
        swapChain = legacySwapChain(activeEngine, activeSurface)
        attachPending = swapChain == null
    }

    @Suppress("DEPRECATION")
    private fun supportedMsaa(activeEngine: Engine): Boolean =
        runCatching { SwapChain.isMSAASwapChainSupported(activeEngine, MSAA_SAMPLES) }
            .getOrDefault(false)

    @Suppress("DEPRECATION")
    private fun legacySwapChain(activeEngine: Engine, activeSurface: Surface): SwapChain? {
        val flags = if (supportedMsaa(activeEngine)) {
            SwapChainFlags.CONFIG_MSAA_4_SAMPLES
        } else {
            SwapChainFlags.CONFIG_DEFAULT
        }
        return runCatching { activeEngine.createSwapChain(activeSurface, flags) }.getOrNull()
    }

    fun install(payload: ByteArray) {
        if (destroyed) return
        if (engine == null) boot()
        val activeEngine = engine ?: return
        val activeScene = filamentScene ?: return
        releaseContent()
        val built = Material.Builder()
            .payload(java.nio.ByteBuffer.wrap(payload), payload.size)
            .build(activeEngine)
        material = built
        for (batch in geometry.batches) {
            installBatch(activeEngine, activeScene, built, batch)
        }
        installPointLights(activeEngine, activeScene)
        ensureLoop()
    }

    private fun boot() {
        runCatching { Filament.init() }
        val activeEngine = Engine.create()
        engine = activeEngine
        renderer = activeEngine.createRenderer()
        val activeScene = activeEngine.createScene()
        filamentScene = activeScene
        val activeView = activeEngine.createView()
        view = activeView
        activeView.scene = activeScene
        activeView.setDithering(FilamentView.Dithering.TEMPORAL)
        activeView.setShadowingEnabled(true)
        msaaActive = supportedMsaa(activeEngine)
        applyAntiAliasing()
        configureFog(activeView)
        installLighting(activeEngine, activeScene)
        installColorGrading(activeEngine, activeView)
        val entity = EntityManager.get().create()
        cameraEntity = entity
        camera = activeEngine.createCamera(entity)
        activeView.camera = camera
    }

    @Suppress("DEPRECATION")
    private fun applyAntiAliasing() {
        val activeView = view ?: return
        activeView.setPostProcessingEnabled(true)
        activeView.setAntiAliasing(
            if (msaaActive) FilamentView.AntiAliasing.NONE else FilamentView.AntiAliasing.FXAA,
        )
    }

    private fun configureFog(activeView: FilamentView) {
        val fog = sceneData.fog
        val background = fog?.let { MapPalette.parseColor(it.color) }
            ?: floatArrayOf(0.04f, 0.05f, 0.07f)
        val options = FilamentView.FogOptions()
        options.enabled = fog != null
        options.density = ((fog?.density ?: 0.02f) * 3f).coerceIn(0.02f, 0.5f)
        options.color = background
        options.height = 0f
        options.heightFalloff = 0.1f
        options.maximumOpacity = 0.82f
        options.inScatteringStart = 0f
        options.inScatteringSize = 0f
        options.fogColorFromIbl = false
        activeView.fogOptions = options
        val clear = Renderer.ClearOptions()
        clear.clear = true
        clear.clearColor = doubleArrayOf(
            background[0].toDouble(),
            background[1].toDouble(),
            background[2].toDouble(),
            1.0,
        )
        renderer?.clearOptions = clear
    }

    private fun installLighting(activeEngine: Engine, activeScene: Scene) {
        val indirect = IndirectLight.Builder()
            .irradiance(
                SH_BAND_COUNT,
                irradianceSH(0.92f, 0.24f),
            )
            .radiance(
                SH_BAND_COUNT,
                radianceSH(0.92f, 0.24f),
            )
            .intensity(9_000f)
            .build(activeEngine)
        indirectLight = indirect
        activeScene.indirectLight = indirect
        val entity = EntityManager.get().create()
        keyLight = entity
        val shadows = LightManager.ShadowOptions()
        shadows.mapSize = 1024
        shadows.shadowCascades = 1
        shadows.constantBias = 0.01f
        shadows.normalBias = 1.2f
        shadows.shadowNearHint = 0.5f
        shadows.shadowFarHint = max(30f, geometry.radiusM * 2f)
        shadows.stepCount = 8
        shadows.maxShadowDistance = max(30f, geometry.radiusM * 3f)
        LightManager.Builder(LightManager.Type.DIRECTIONAL)
            .color(1f, 0.95f, 0.86f)
            .intensity(58_000f)
            .direction(0.42f, -0.82f, -0.36f)
            .castShadows(true)
            .shadowOptions(shadows)
            .build(activeEngine, entity)
        activeScene.addEntity(entity)
    }

    @Suppress("DEPRECATION")
    private fun installColorGrading(activeEngine: Engine, activeView: FilamentView) {
        val grading = ColorGrading.Builder()
            .toneMapping(ColorGrading.ToneMapping.ACES)
            .exposure(-0.22f)
            .contrast(1.05f)
            .vibrance(1.06f)
            .build(activeEngine)
        colorGrading = grading
        activeView.colorGrading = grading
    }

    private fun installBatch(
        activeEngine: Engine,
        activeScene: Scene,
        built: Material,
        batch: MapGeometryBatch,
    ) {
        val vertexCount = batch.vertexCount
        if (vertexCount == 0 || batch.indices.isEmpty()) return
        val vertexData = FloatBuffer.allocate(vertexCount * 9)
        var minX = Float.MAX_VALUE
        var minY = Float.MAX_VALUE
        var minZ = Float.MAX_VALUE
        var maxX = -Float.MAX_VALUE
        var maxY = -Float.MAX_VALUE
        var maxZ = -Float.MAX_VALUE
        for (i in 0 until vertexCount) {
            val px = batch.positions[i * 3]
            val py = batch.positions[i * 3 + 1]
            val pz = batch.positions[i * 3 + 2]
            vertexData.put(px)
            vertexData.put(py)
            vertexData.put(pz)
            vertexData.put(batch.normals[i * 3])
            vertexData.put(batch.normals[i * 3 + 1])
            vertexData.put(batch.normals[i * 3 + 2])
            vertexData.put(1f)
            vertexData.put(batch.uvs[i * 2])
            vertexData.put(batch.uvs[i * 2 + 1])
            minX = minOf(minX, px)
            minY = minOf(minY, py)
            minZ = minOf(minZ, pz)
            maxX = maxOf(maxX, px)
            maxY = maxOf(maxY, py)
            maxZ = maxOf(maxZ, pz)
        }
        vertexData.rewind()
        val vertexBuffer = VertexBuffer.Builder()
            .vertexCount(vertexCount)
            .bufferCount(1)
            .attribute(
                VertexBuffer.VertexAttribute.POSITION,
                0,
                VertexBuffer.AttributeType.FLOAT3,
                0,
                VERTEX_STRIDE,
            )
            .attribute(
                VertexBuffer.VertexAttribute.TANGENTS,
                0,
                VertexBuffer.AttributeType.FLOAT4,
                12,
                VERTEX_STRIDE,
            )
            .attribute(
                VertexBuffer.VertexAttribute.UV0,
                0,
                VertexBuffer.AttributeType.FLOAT2,
                28,
                VERTEX_STRIDE,
            )
            .build(activeEngine)
        vertexBuffer.setBufferAt(activeEngine, 0, vertexData)
        val indexBuffer = IndexBuffer.Builder()
            .indexCount(batch.indices.size)
            .bufferType(IndexBuffer.Builder.IndexType.UINT)
            .build(activeEngine)
        indexBuffer.setBuffer(activeEngine, IntBuffer.wrap(batch.indices))
        val store = DioramaBuffers(vertexBuffer, indexBuffer)
        buffers.add(store)
        val instance = built.createInstance()
        val color = MapPalette.colorFor(batch.kind)
        instance.setParameter("baseColor", color[0], color[1], color[2], 1f)
        instance.setParameter("roughness", MapPalette.roughnessFor(batch.kind))
        instance.setParameter("metallic", MapPalette.metallicFor(batch.kind))
        instances.add(instance)
        val entity = EntityManager.get().create()
        renderables.add(entity)
        RenderableManager.Builder(1)
            .boundingBox(
                FilamentBox(
                    (minX + maxX) * 0.5f,
                    (minY + maxY) * 0.5f,
                    (minZ + maxZ) * 0.5f,
                    (maxX - minX) * 0.5f + 0.01f,
                    (maxY - minY) * 0.5f + 0.01f,
                    (maxZ - minZ) * 0.5f + 0.01f,
                ),
            )
            .geometry(0, RenderableManager.PrimitiveType.TRIANGLES, vertexBuffer, indexBuffer)
            .material(0, instance)
            .culling(true)
            .castShadows(batch.kind != MapSurfaceKind.GROUND)
            .receiveShadows(true)
            .build(activeEngine, entity)
        activeScene.addEntity(entity)
    }

    private fun installPointLights(activeEngine: Engine, activeScene: Scene) {
        val tile = geometry.tileM
        for (light in sceneData.lights.take(8)) {
            if (light.x !in 0 until geometry.width || light.y !in 0 until geometry.height) continue
            val level = sceneData.heightmap.getOrNull(light.y)?.getOrNull(light.x) ?: 0
            val y = level.coerceIn(0, MapGeometryBuilder.MAX_LEVEL) *
                MapGeometryBuilder.LEVEL_M + 1.1f
            val x = (light.x - geometry.width / 2f + 0.5f) * tile
            val z = (light.y - geometry.height / 2f + 0.5f) * tile
            val color = MapPalette.parseColor(light.color)
                ?: floatArrayOf(1f, 0.60f, 0.24f)
            val entity = EntityManager.get().create()
            pointLights.add(entity)
            LightManager.Builder(LightManager.Type.POINT)
                .color(color[0], color[1], color[2])
                .intensity(16_000f)
                .falloff(light.radiusM.coerceIn(1.5f, 8f))
                .position(x, y, z)
                .castShadows(false)
                .build(activeEngine, entity)
            activeScene.addEntity(entity)
        }
    }

    private fun project() {
        val activeCamera = camera ?: return
        if (viewportWidth > 0 && viewportHeight > 0) {
            activeCamera.setProjection(
                45.0,
                viewportWidth.toDouble() / viewportHeight,
                0.1,
                max(80.0, distance.toDouble() + geometry.radiusM * 4.0),
                Camera.Fov.VERTICAL,
            )
        }
        val cp = cos(pitch)
        val eyeX = distance * cp * sin(yaw)
        val eyeY = focusY + distance * sin(pitch)
        val eyeZ = distance * cp * cos(yaw)
        activeCamera.lookAt(
            eyeX.toDouble(),
            eyeY.toDouble(),
            eyeZ.toDouble(),
            0.0,
            focusY.toDouble(),
            0.0,
            0.0,
            1.0,
            0.0,
        )
    }

    private fun releaseContent() {
        val activeEngine = engine ?: return
        val activeScene = filamentScene ?: return
        for (entity in renderables) {
            runCatching { activeScene.removeEntity(entity) }
            runCatching { activeEngine.getRenderableManager().destroy(entity) }
            runCatching { EntityManager.get().destroy(entity) }
        }
        renderables.clear()
        for (store in buffers) {
            runCatching { activeEngine.destroyVertexBuffer(store.vertex) }
            runCatching { activeEngine.destroyIndexBuffer(store.index) }
        }
        buffers.clear()
        for (instance in instances) {
            runCatching { activeEngine.destroyMaterialInstance(instance) }
        }
        instances.clear()
        material?.let { runCatching { activeEngine.destroyMaterial(it) } }
        material = null
        for (entity in pointLights) {
            runCatching { activeScene.removeEntity(entity) }
            runCatching { activeEngine.getLightManager().destroy(entity) }
            runCatching { EntityManager.get().destroy(entity) }
        }
        pointLights.clear()
    }

    fun destroy() {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            mainHandler.post { destroy() }
            return
        }
        if (destroyed) return
        destroyed = true
        pause()
        val activeEngine = engine ?: return
        swapChain?.let { runCatching { activeEngine.destroySwapChain(it) } }
        swapChain = null
        runCatching { activeEngine.flushAndWait() }
        releaseContent()
        filamentScene?.let { runCatching { activeEngine.destroyScene(it) } }
        filamentScene = null
        view?.let { runCatching { activeEngine.destroyView(it) } }
        view = null
        indirectLight?.let { runCatching { activeEngine.destroyIndirectLight(it) } }
        indirectLight = null
        colorGrading?.let { runCatching { activeEngine.destroyColorGrading(it) } }
        colorGrading = null
        if (keyLight != 0) {
            runCatching { activeEngine.getLightManager().destroy(keyLight) }
            runCatching { EntityManager.get().destroy(keyLight) }
        }
        keyLight = 0
        if (cameraEntity != 0) {
            runCatching { activeEngine.destroyCameraComponent(cameraEntity) }
            runCatching { EntityManager.get().destroy(cameraEntity) }
        }
        cameraEntity = 0
        camera = null
        renderer?.let { runCatching { activeEngine.destroyRenderer(it) } }
        renderer = null
        runCatching { activeEngine.flushAndWait() }
        runCatching { activeEngine.destroy() }
        engine = null
    }
}

private fun irradianceSH(upper: Float, lower: Float): FloatArray =
    basisSH(SH_DC_FLOOR * (upper + lower), SH_Y_FLOOR * (upper - lower))

private fun radianceSH(upper: Float, lower: Float): FloatArray =
    basisSH(SH_DC_SCALE * (upper + lower), SH_Y_SCALE * (upper - lower))

private fun basisSH(dc: Float, y: Float): FloatArray {
    val sh = FloatArray(SH_COEFFICIENTS)
    sh[0] = dc
    sh[1] = dc
    sh[2] = dc
    sh[3] = y
    sh[4] = y
    sh[5] = y
    return sh
}
