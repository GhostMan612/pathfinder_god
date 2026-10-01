// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import android.graphics.PixelFormat
import android.view.Choreographer
import android.view.Surface
import android.view.SurfaceHolder
import android.view.SurfaceView
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.google.android.filament.Camera
import com.google.android.filament.ColorGrading
import com.google.android.filament.Engine
import com.google.android.filament.EntityManager
import com.google.android.filament.Filament
import com.google.android.filament.IndexBuffer
import com.google.android.filament.IndirectLight
import com.google.android.filament.LightManager
import com.google.android.filament.Material
import com.google.android.filament.MaterialInstance
import com.google.android.filament.RenderableManager
import com.google.android.filament.Renderer
import com.google.android.filament.Scene
import com.google.android.filament.SwapChain
import com.google.android.filament.SwapChainFlags
import com.google.android.filament.Texture
import com.google.android.filament.TextureSampler
import com.google.android.filament.VertexBuffer
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.ui.designsystem.GodStatusText
import com.pathfindergod.spoke.ui.dice.Die
import com.pathfindergod.spoke.ui.dice.Impact
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.nio.ByteBuffer
import java.nio.FloatBuffer
import java.nio.ShortBuffer
import kotlin.math.exp
import kotlin.random.Random
import com.google.android.filament.Box as FilamentBox
import com.google.android.filament.View as FilamentView

private const val DIE_Y = PitWorld.DIE_Y
private const val GROUND_Y = PitWorld.GROUND_Y
private const val DISC_Y = PitWorld.DISC_Y
private const val GROUND_HALF = PitWorld.GROUND_HALF
private const val DISC_RADIUS = PitWorld.DISC_RADIUS
private const val DISC_SEGMENTS = PitWorld.DISC_SEGMENTS
private const val GROUND_TILES = PitWorld.GROUND_TILES
private const val FOCUS_Y = PitWorld.FOCUS_Y
private const val MIN_DISTANCE = PitWorld.MIN_DISTANCE
private const val MAX_DISTANCE = PitWorld.MAX_DISTANCE
private const val MIN_PITCH = PitWorld.MIN_PITCH
private const val MAX_PITCH = PitWorld.MAX_PITCH
private const val MSAA_SAMPLES = PitRenderConfig.MSAA_SAMPLES
private const val ANISOTROPY = PitRenderConfig.ANISOTROPY
private const val ATTACH_RETRY_MS = 250L
private const val TUMBLE_MS = 850L
private const val SPIN_DECAY = 2.4f
private const val SPIN_SETTLE = 3.2f
private const val SETTLE_MS = 1_100L
private const val DRAMATIC_SETTLE_MS = 1_650L
private const val DIE_STRIDE = 44
private const val DIE_FLOATS = 11
private const val QUAD_STRIDE = 20
private const val QUAD_FLOATS = 5
private const val SH_BAND_COUNT = 3
private const val SH_COEFFICIENTS = 9
private const val SH_DC_SCALE = 1.772454f
private const val SH_Y_SCALE = -1.023390f
private const val SH_DC_FLOOR = 0.5f
private const val SH_Y_FLOOR = 1f / 3f

object PitLighting {
    const val KEY_LUX = 52_000f
    const val AMBIENT_LUX = 7_500f
    const val UPPER_RADIANCE = 0.95f
    const val LOWER_RADIANCE = 0.28f
    const val EXPOSURE = -0.30f
}

private class PitAssets(
    val die: Die,
    val mesh: DieMesh,
    val baseColor: List<AtlasLevel>,
    val normal: List<AtlasLevel>,
    val felt: List<AtlasLevel>,
    val shadow: List<AtlasLevel>,
    val payloads: Map<PitMaterial.Kind, ByteArray>,
    val discardOnChange: Boolean,
)

private class PitBuffers(
    val vertex: VertexBuffer,
    val index: IndexBuffer,
)

private class PitUpload(var buffer: ByteBuffer? = null) {
    fun level(rgba: ByteArray): ByteBuffer {
        val capacity = rgba.size
        val current = buffer
        val target = if (current != null && current.capacity() >= capacity) {
            current
        } else {
            ByteBuffer.allocateDirect(capacity)
        }
        target.clear()
        target.put(rgba)
        target.position(0)
        target.limit(capacity)
        buffer = target
        return target
    }
}

private class PitRig {
    var engine: Engine? = null
    var renderer: Renderer? = null
    var scene: Scene? = null
    var view: FilamentView? = null
    var camera: Camera? = null
    var swapChain: SwapChain? = null
    var colorGrading: ColorGrading? = null
    var indirectLight: IndirectLight? = null
    var materials: Map<PitMaterial.Kind, Material> = emptyMap()
    var dieInstance: MaterialInstance? = null
    var feltInstance: MaterialInstance? = null
    var shadowInstance: MaterialInstance? = null
    var dieBuffers: PitBuffers? = null
    var groundBuffers: PitBuffers? = null
    var discBuffers: PitBuffers? = null
    var baseColorTexture: Texture? = null
    var normalTexture: Texture? = null
    var feltTexture: Texture? = null
    var discTexture: Texture? = null
    var mesh: DieMesh? = null
    var currentDie: Die? = null
    var surface: Surface? = null
    var renderable = 0
    var groundRenderable = 0
    var discRenderable = 0
    var keyLight = 0
    var cameraEntity = 0
    var viewportWidth = 1
    var viewportHeight = 1
    var refreshRate = 60f
    var running = false
    var attachPending = false
    var attachRetryAt = 0L
    var lastNanos = 0L
    var orientation = PitTransform.identity()
    var settleFrom = PitTransform.identity()
    var settleTo = PitTransform.identity()
    var settleStart = 0L
    var settleDuration = SETTLE_MS
    var tumbling = false
    var settling = false
    var spinAxis = floatArrayOf(0.3f, 0.8f, 0.5f)
    var spinSpeed = 0f
    var tumbleUntil = 0L
    var pendingFace = 0
    var dramatic = false
    var impactPending = true
    var onImpact: () -> Unit = {}
    var orbitYaw = PitWorld.DEFAULT_YAW
    var orbitPitch = PitWorld.DEFAULT_PITCH
    var orbitDistance = PitWorld.DEFAULT_DISTANCE
    var destroyed = false
    var upload: PitUpload? = null
    var msaaActive = false

    val frame = object : Choreographer.FrameCallback {
        override fun doFrame(now: Long) {
            if (!running) return
            Choreographer.getInstance().postFrameCallback(this)
            step(now)
            PitFrameGovernor.sampleFrame(now)
        }
    }

    fun eye(): FloatArray = PitWorld.eye(orbitYaw, orbitPitch, orbitDistance)

    fun roll(dramaticRoll: Boolean, value: Int, fire: () -> Unit) {
        val jitter = Random.nextFloat() - 0.5f
        spinAxis = PitTransform.normalizeDirection(
            floatArrayOf(0.35f + jitter, 0.75f + jitter * 0.4f, 0.55f - jitter),
        )
        spinSpeed = if (dramaticRoll) 16f else 10f
        tumbling = true
        settling = false
        dramatic = dramaticRoll
        pendingFace = value
        tumbleUntil = System.nanoTime() + TUMBLE_MS * 1_000_000L
        impactPending = false
        onImpact = fire
    }

    fun orbit(panX: Float, panY: Float, zoom: Float) {
        orbitYaw -= panX * 0.010f
        orbitPitch = (orbitPitch + panY * 0.010f).coerceIn(MIN_PITCH, MAX_PITCH)
        if (zoom > 0.0001f) {
            orbitDistance = (orbitDistance / zoom).coerceIn(MIN_DISTANCE, MAX_DISTANCE)
        }
    }

    fun step(now: Long) {
        val dt = if (lastNanos == 0L) {
            PitFrameGovernor.swapIntervalSeconds()
        } else {
            ((now - lastNanos) / 1_000_000_000.0).toFloat()
                .coerceIn(0f, PitFrameGovernor.dtCeiling())
        }
        lastNanos = now
        if (swapChain == null) {
            attach(now)
            if (swapChain == null) return
        }
        advance(dt, now)
        project()
        val renderer = renderer ?: return
        val swapChain = swapChain ?: return
        val view = view ?: return
        if (renderer.beginFrame(swapChain, now)) {
            renderer.render(view)
            renderer.endFrame()
        }
    }

    fun attach(now: Long) {
        if (swapChain != null) {
            attachPending = false
            return
        }
        if (engine == null || surface == null) {
            attachPending = true
            return
        }
        if (attachPending && now < attachRetryAt) return
        attachRetryAt = now + ATTACH_RETRY_MS * 1_000_000L
        val activeEngine = engine ?: return
        val surface = surface ?: return
        msaaActive = supportedMsaa(activeEngine)
        swapChain = legacySwapChain(activeEngine, surface)
        attachPending = swapChain == null
    }

    @Suppress("DEPRECATION")
    private fun supportedMsaa(activeEngine: Engine): Boolean =
        runCatching { SwapChain.isMSAASwapChainSupported(activeEngine, MSAA_SAMPLES) }
            .getOrDefault(false)

    @Suppress("DEPRECATION")
    private fun legacySwapChain(activeEngine: Engine, surface: Surface): SwapChain? {
        val flags = if (supportedMsaa(activeEngine)) {
            SwapChainFlags.CONFIG_MSAA_4_SAMPLES
        } else {
            SwapChainFlags.CONFIG_DEFAULT
        }
        return runCatching { activeEngine.createSwapChain(surface, flags) }.getOrNull()
    }

    fun ensureLoop() {
        if (running || destroyed || engine == null) return
        running = true
        lastNanos = 0L
        Choreographer.getInstance().postFrameCallback(frame)
    }

    fun pause() {
        if (!running) return
        running = false
        Choreographer.getInstance().removeFrameCallback(frame)
    }

    fun resize(width: Int, height: Int) {
        if (width <= 0 || height <= 0) return
        viewportWidth = width
        viewportHeight = height
    }

    fun destroy() {
        if (destroyed) return
        destroyed = true
        pause()
        upload = null
        val activeEngine = engine ?: return
        swapChain?.let { runCatching { activeEngine.destroySwapChain(it) } }
        swapChain = null
        activeEngine.flushAndWait()
        releaseRenderables()
        releaseScene()
        releaseBuffers()
        releaseMaterials()
        view?.let { runCatching { activeEngine.destroyView(it) } }
        view = null
        scene?.let { runCatching { activeEngine.destroyScene(it) } }
        scene = null
        renderer?.let { runCatching { activeEngine.destroyRenderer(it) } }
        renderer = null
        activeEngine.flushAndWait()
        runCatching { activeEngine.destroy() }
        engine = null
    }

    private fun advance(dt: Float, now: Long) {
        if (tumbling) {
            spinSpeed *= exp(-dt * SPIN_DECAY)
            val turn = PitTransform.axisAngle(spinAxis, spinSpeed * dt)
            orientation = PitTransform.normalize(
                PitTransform.multiply(turn, orientation),
            )
            if (now >= tumbleUntil && spinSpeed < SPIN_SETTLE) beginSettle(now)
            return
        }
        if (!settling) return
        val elapsed = (now - settleStart).toFloat() / 1_000_000f
        val raw = (elapsed / settleDuration).coerceIn(0f, 1f)
        orientation = PitTransform.slerp(settleFrom, settleTo, raw * raw * (3f - 2f * raw))
        if (raw >= 1f) settling = false
    }

    private fun beginSettle(now: Long) {
        tumbling = false
        if (!impactPending) {
            impactPending = true
            onImpact()
        }
        val normal = mesh?.centroidNormalFor(pendingFace)
        if (normal == null) {
            settling = false
            return
        }
        val towardsCamera = PitTransform.normalizeDirection(PitWorld.toDieDirection(eye()))
        settleTo = PitTransform.settleQuaternion(orientation, normal, towardsCamera)
        settleFrom = orientation
        settleStart = now
        settleDuration = if (dramatic) DRAMATIC_SETTLE_MS else SETTLE_MS
        settling = true
    }

    private fun project() {
        val engine = engine ?: return
        val camera = camera ?: return
        if (viewportWidth > 0 && viewportHeight > 0) {
            camera.setProjection(
                42.0,
                viewportWidth.toDouble() / viewportHeight,
                0.1,
                40.0,
                Camera.Fov.VERTICAL,
            )
        }
        val eye = eye()
        camera.lookAt(
            eye[0].toDouble(), eye[1].toDouble(), eye[2].toDouble(),
            0.0, FOCUS_Y.toDouble(), 0.0,
            0.0, 1.0, 0.0,
        )
        if (renderable == 0) return
        val matrix = PitTransform.toFilamentMatrix(orientation, 0f, DIE_Y, 0f)
        engine.getTransformManager().setTransform(renderable, matrix)
    }

    internal fun releaseRenderables() {
        val engine = engine ?: return
        val scene = scene ?: return
        listOf(renderable, groundRenderable, discRenderable).filter { it != 0 }.forEach { entity ->
            runCatching { scene.removeEntity(entity) }
            runCatching { engine.getRenderableManager().destroy(entity) }
            runCatching { EntityManager.get().destroy(entity) }
        }
        renderable = 0
        groundRenderable = 0
        discRenderable = 0
    }

    private fun releaseScene() {
        val engine = engine ?: return
        val scene = scene ?: return
        scene.setIndirectLight(null)
        indirectLight?.let { runCatching { engine.destroyIndirectLight(it) } }
        indirectLight = null
        view?.setColorGrading(null)
        colorGrading?.let { runCatching { engine.destroyColorGrading(it) } }
        colorGrading = null
        if (keyLight != 0) {
            runCatching { scene.removeEntity(keyLight) }
            runCatching { engine.getLightManager().destroy(keyLight) }
            runCatching { EntityManager.get().destroy(keyLight) }
        }
        keyLight = 0
        if (cameraEntity != 0) {
            runCatching { engine.destroyCameraComponent(cameraEntity) }
            runCatching { EntityManager.get().destroy(cameraEntity) }
        }
        cameraEntity = 0
        camera = null
    }

    internal fun releaseBuffers() {
        val engine = engine ?: return
        listOf(dieBuffers, groundBuffers, discBuffers).filterNotNull().forEach { buffers ->
            runCatching { engine.destroyVertexBuffer(buffers.vertex) }
            runCatching { engine.destroyIndexBuffer(buffers.index) }
        }
        dieBuffers = null
        groundBuffers = null
        discBuffers = null
        listOf(baseColorTexture, normalTexture, feltTexture, discTexture)
            .filterNotNull()
            .forEach { runCatching { engine.destroyTexture(it) } }
        baseColorTexture = null
        normalTexture = null
        feltTexture = null
        discTexture = null
    }

    internal fun releaseMaterials() {
        val engine = engine ?: return
        listOf(dieInstance, feltInstance, shadowInstance).filterNotNull().forEach {
            runCatching { engine.destroyMaterialInstance(it) }
        }
        dieInstance = null
        feltInstance = null
        shadowInstance = null
        materials.values.forEach { runCatching { engine.destroyMaterial(it) } }
        materials = emptyMap()
    }
}

@Composable
fun FilamentPit(
    die: Die,
    face: Int,
    rollToken: Int,
    impact: Impact = Impact.NORMAL,
    modifier: Modifier = Modifier,
    onImpact: () -> Unit = {},
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val rig = remember { PitRig() }
    var failed by remember { mutableStateOf(false) }
    Box(
        modifier = modifier.pointerInput(Unit) {
            detectTransformGestures { _, pan, zoom, _ -> rig.orbit(pan.x, pan.y, zoom) }
        },
        contentAlignment = Alignment.Center,
    ) {
        AndroidView(
            factory = { ctx ->
                SurfaceView(ctx).also { view ->
                    view.holder.setFormat(PixelFormat.RGBA_8888)
                    rig.refreshRate = PitFrameGovernor.refreshRateOf(view.display)
                    view.holder.addCallback(object : SurfaceHolder.Callback {
                        override fun surfaceCreated(holder: SurfaceHolder) {
                            rig.surface = holder.surface
                            PitFrameGovernor.applyToSurface(holder.surface)
                            rig.attach(System.nanoTime())
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
                            rig.surface = null
                            rig.attachRetryAt = 0L
                            val engine = rig.engine
                            rig.swapChain?.let {
                                runCatching { engine?.destroySwapChain(it) }
                            }
                            rig.swapChain = null
                            engine?.flushAndWait()
                        }
                    })
                }
            },
            modifier = Modifier.fillMaxSize(),
        )
        if (failed) {
            GodStatusText(text = stringResource(R.string.pit_failed))
        }
    }
    LaunchedEffect(die) {
        val assets = withContext(Dispatchers.Default) { prepareAssets(context, die) }
        if (assets == null) {
            failed = true
            return@LaunchedEffect
        }
        try {
            rig.install(assets)
            failed = false
        } catch (_: Throwable) {
            failed = true
        }
    }
    LaunchedEffect(rollToken) {
        if (rollToken == 0) return@LaunchedEffect
        rig.roll(impact != Impact.NORMAL, face, onImpact)
    }
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> rig.ensureLoop()
                Lifecycle.Event.ON_STOP -> rig.pause()
                else -> Unit
            }
        }
        val client = object : PitFrameClient {
            override fun onHostResume(refreshRate: Float) {
                rig.refreshRate = refreshRate
                rig.refreshDisplay()
                rig.ensureLoop()
            }

            override fun onHostPause() {
                rig.pause()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        PitFrameGovernor.attach(client)
        onDispose {
            PitFrameGovernor.detach(client)
            lifecycleOwner.lifecycle.removeObserver(observer)
            rig.destroy()
        }
    }
}

private fun prepareAssets(context: android.content.Context, die: Die): PitAssets? = try {
    val mesh = DieMeshBuilder.build(die)
    val payloads = PitMaterial.prepare(
        context,
        listOf(PitMaterial.Kind.DIE, PitMaterial.Kind.FELT, PitMaterial.Kind.SHADOW),
    )
    if (payloads.size != 3) {
        null
    } else {
        PitAssets(
            die = die,
            mesh = mesh,
            baseColor = DieTexture.baseColorLevels(mesh),
            normal = DieTexture.normalLevels(mesh),
            felt = DieTexture.feltLevels(),
            shadow = DieTexture.shadowLevels(),
            payloads = payloads,
            discardOnChange = PitRenderConfig.DISCARDS_ON_DIE_CHANGE,
        )
    }
} catch (_: Throwable) {
    null
}

private fun PitRig.install(assets: PitAssets) {
    val booted = engine == null
    if (booted) {
        boot(assets)
    } else {
        releaseRenderables()
        releaseBuffers()
        releaseMaterials()
        installMaterials(engine!!, assets)
    }
    installDie(assets)
    installGround(assets)
    if (!assets.discardOnChange || booted) installDisc(assets)
    mesh = assets.mesh
    currentDie = assets.die
    refreshDisplay()
    applyAntiAliasing()
    attach(System.nanoTime())
    ensureLoop()
}

private fun PitRig.boot(assets: PitAssets) {
    runCatching { Filament.init() }
    val engine = Engine.create()
    this.engine = engine
    val renderer = engine.createRenderer()
    this.renderer = renderer
    val scene = engine.createScene()
    this.scene = scene
    val view = engine.createView()
    this.view = view
    view.scene = scene
    val cameraEntity = EntityManager.get().create()
    this.cameraEntity = cameraEntity
    val camera = engine.createCamera(cameraEntity)
    this.camera = camera
    view.camera = camera
    view.setDithering(FilamentView.Dithering.TEMPORAL)
    view.setShadowingEnabled(true)
    applyAntiAliasing()
    installLighting(engine, scene)
    installColorGrading(engine, view)
    installMaterials(engine, assets)
}

@Suppress("DEPRECATION")
private fun PitRig.applyAntiAliasing() {
    val view = view ?: return
    view.setPostProcessingEnabled(true)
    view.setAntiAliasing(
        if (msaaActive) FilamentView.AntiAliasing.NONE else FilamentView.AntiAliasing.FXAA,
    )
}

private fun PitRig.refreshDisplay() {
    val renderer = renderer ?: return
    val info = Renderer.DisplayInfo()
    info.refreshRate = refreshRate
    renderer.setDisplayInfo(info)
}

private fun PitRig.installLighting(engine: Engine, scene: Scene) {
    val indirect = IndirectLight.Builder()
        .irradiance(
            SH_BAND_COUNT,
            irradianceSH(PitLighting.UPPER_RADIANCE, PitLighting.LOWER_RADIANCE),
        )
        .radiance(
            SH_BAND_COUNT,
            radianceSH(PitLighting.UPPER_RADIANCE, PitLighting.LOWER_RADIANCE),
        )
        .intensity(PitLighting.AMBIENT_LUX)
        .build(engine)
    indirectLight = indirect
    scene.setIndirectLight(indirect)
    val lightEntity = EntityManager.get().create()
    keyLight = lightEntity
    val shadows = LightManager.ShadowOptions()
    shadows.mapSize = PitRenderConfig.SHADOW_MAP_SIZE
    shadows.shadowCascades = 1
    shadows.constantBias = 0.006f
    shadows.normalBias = 1.0f
    shadows.shadowNearHint = 0.5f
    shadows.shadowFarHint = 8f
    shadows.screenSpaceContactShadows = true
    shadows.stepCount = PitRenderConfig.SHADOW_STEP_COUNT
    shadows.maxShadowDistance = 0.45f
    LightManager.Builder(LightManager.Type.DIRECTIONAL)
        .color(1f, 0.96f, 0.88f)
        .intensity(PitLighting.KEY_LUX)
        .direction(0.40f, -0.85f, -0.35f)
        .castShadows(true)
        .shadowOptions(shadows)
        .build(engine, lightEntity)
    scene.addEntity(lightEntity)
}

@Suppress("DEPRECATION")
private fun PitRig.installColorGrading(engine: Engine, view: FilamentView) {
    val grading = ColorGrading.Builder()
        .toneMapping(ColorGrading.ToneMapping.ACES)
        .exposure(PitLighting.EXPOSURE)
        .contrast(1.05f)
        .vibrance(1.06f)
        .build(engine)
    colorGrading = grading
    view.setColorGrading(grading)
}

private fun PitRig.installMaterials(engine: Engine, assets: PitAssets) {
    val built = LinkedHashMap<PitMaterial.Kind, Material>()
    assets.payloads.forEach { entry ->
        val payload = entry.value
        built[entry.key] = Material.Builder()
            .payload(ByteBuffer.wrap(payload), payload.size)
            .build(engine)
    }
    materials = built
    val die = built.getValue(PitMaterial.Kind.DIE).createInstance()
    die.setParameter("roughness", PitMaterial.ROUGHNESS)
    die.setParameter("metallic", PitMaterial.METALLIC)
    dieInstance = die
    feltInstance = built.getValue(PitMaterial.Kind.FELT).createInstance()
    shadowInstance = built.getValue(PitMaterial.Kind.SHADOW).createInstance()
}

private fun PitRig.installDie(assets: PitAssets) {
    val engine = engine ?: return
    val scene = scene ?: return
    val instance = dieInstance ?: return
    val mesh = assets.mesh
    val vertices = mesh.indices.size
    val data = FloatBuffer.allocate(vertices * DIE_FLOATS)
    for (v in 0 until vertices) {
        data.put(mesh.positions[v * 3])
        data.put(mesh.positions[v * 3 + 1])
        data.put(mesh.positions[v * 3 + 2])
        data.put(mesh.tangents[v * 4])
        data.put(mesh.tangents[v * 4 + 1])
        data.put(mesh.tangents[v * 4 + 2])
        data.put(mesh.tangents[v * 4 + 3])
        data.put(mesh.uvs[v * 2])
        data.put(mesh.uvs[v * 2 + 1])
    }
    data.rewind()
    val vertexBuffer = VertexBuffer.Builder()
        .vertexCount(vertices)
        .bufferCount(1)
        .attribute(
            VertexBuffer.VertexAttribute.POSITION,
            0,
            VertexBuffer.AttributeType.FLOAT3,
            0,
            DIE_STRIDE,
        )
        .attribute(
            VertexBuffer.VertexAttribute.TANGENTS,
            0,
            VertexBuffer.AttributeType.FLOAT4,
            12,
            DIE_STRIDE,
        )
        .attribute(
            VertexBuffer.VertexAttribute.UV0,
            0,
            VertexBuffer.AttributeType.FLOAT2,
            28,
            DIE_STRIDE,
        )
        .build(engine)
    vertexBuffer.setBufferAt(engine, 0, data)
    val buffers = PitBuffers(vertexBuffer, buildIndexBuffer(engine, mesh.indices))
    dieBuffers = buffers
    val color = uploadMips(engine, assets.baseColor, true)
    val normal = uploadMips(engine, assets.normal, false)
    baseColorTexture = color
    normalTexture = normal
    instance.setParameter("baseColorMap", color, clampSampler())
    instance.setParameter("normalMap", normal, clampSampler())
    val entity = EntityManager.get().create()
    renderable = entity
    RenderableManager.Builder(1)
        .boundingBox(
            FilamentBox(
                0f, 0f, 0f,
                PitWorld.DIE_RADIUS, PitWorld.DIE_RADIUS, PitWorld.DIE_RADIUS,
            ),
        )
        .geometry(0, RenderableManager.PrimitiveType.TRIANGLES, buffers.vertex, buffers.index)
        .material(0, instance)
        .culling(true)
        .castShadows(true)
        .receiveShadows(true)
        .build(engine, entity)
    scene.addEntity(entity)
}

private fun PitRig.installGround(assets: PitAssets) {
    val engine = engine ?: return
    val scene = scene ?: return
    val instance = feltInstance ?: return
    val buffers = buildQuad(engine, DieAtlas.groundQuad(GROUND_HALF, GROUND_Y, GROUND_TILES))
    groundBuffers = buffers
    val texture = uploadMips(engine, assets.felt, true)
    feltTexture = texture
    instance.setParameter("baseColorMap", texture, tilingSampler())
    val entity = EntityManager.get().create()
    groundRenderable = entity
    RenderableManager.Builder(1)
        .boundingBox(
            FilamentBox(0f, GROUND_Y, 0f, GROUND_HALF, 0.02f, GROUND_HALF),
        )
        .geometry(0, RenderableManager.PrimitiveType.TRIANGLES, buffers.vertex, buffers.index)
        .material(0, instance)
        .culling(true)
        .castShadows(false)
        .receiveShadows(true)
        .build(engine, entity)
    scene.addEntity(entity)
}

private fun PitRig.installDisc(assets: PitAssets) {
    val engine = engine ?: return
    val scene = scene ?: return
    val instance = shadowInstance ?: return
    releaseDisc()
    val buffers = buildQuad(
        engine,
        DieAtlas.contactDisc(DISC_RADIUS, DISC_Y, DISC_SEGMENTS),
    )
    discBuffers = buffers
    val texture = uploadMips(engine, assets.shadow, true)
    discTexture = texture
    instance.setParameter("baseColorMap", texture, clampSampler())
    val entity = EntityManager.get().create()
    discRenderable = entity
    RenderableManager.Builder(1)
        .boundingBox(FilamentBox(0f, DISC_Y, 0f, DISC_RADIUS, 0.02f, DISC_RADIUS))
        .geometry(0, RenderableManager.PrimitiveType.TRIANGLES, buffers.vertex, buffers.index)
        .material(0, instance)
        .culling(true)
        .castShadows(false)
        .receiveShadows(false)
        .build(engine, entity)
    scene.addEntity(entity)
}

private fun buildIndexBuffer(engine: Engine, indices: ShortArray): IndexBuffer {
    val data = ShortBuffer.allocate(indices.size)
    data.put(indices)
    data.rewind()
    val buffer = IndexBuffer.Builder()
        .indexCount(indices.size)
        .bufferType(IndexBuffer.Builder.IndexType.USHORT)
        .build(engine)
    buffer.setBuffer(engine, data)
    return buffer
}

private fun buildQuad(engine: Engine, quad: PitQuad): PitBuffers {
    val vertices = quad.indices.size
    val data = FloatBuffer.allocate(vertices * QUAD_FLOATS)
    for (v in 0 until vertices) {
        data.put(quad.positions[v * 3])
        data.put(quad.positions[v * 3 + 1])
        data.put(quad.positions[v * 3 + 2])
        data.put(quad.uvs[v * 2])
        data.put(quad.uvs[v * 2 + 1])
    }
    data.rewind()
    val vertexBuffer = VertexBuffer.Builder()
        .vertexCount(vertices)
        .bufferCount(1)
        .attribute(
            VertexBuffer.VertexAttribute.POSITION,
            0,
            VertexBuffer.AttributeType.FLOAT3,
            0,
            QUAD_STRIDE,
        )
        .attribute(
            VertexBuffer.VertexAttribute.UV0,
            0,
            VertexBuffer.AttributeType.FLOAT2,
            12,
            QUAD_STRIDE,
        )
        .build(engine)
    vertexBuffer.setBufferAt(engine, 0, data)
    return PitBuffers(vertexBuffer, buildIndexBuffer(engine, quad.indices))
}

private fun PitRig.uploadMips(
    engine: Engine,
    levels: List<AtlasLevel>,
    srgb: Boolean,
): Texture {
    val base = levels.first()
    val texture = Texture.Builder()
        .width(base.width)
        .height(base.height)
        .levels(levels.size)
        .format(
            if (srgb) Texture.InternalFormat.SRGB8_A8 else Texture.InternalFormat.RGBA8,
        )
        .sampler(Texture.Sampler.SAMPLER_2D)
        .build(engine)
    val pool = upload ?: PitUpload().also { upload = it }
    levels.forEachIndexed { index, level ->
        texture.setImage(
            engine,
            index,
            Texture.PixelBufferDescriptor(
                pool.level(level.rgba),
                Texture.Format.RGBA,
                Texture.Type.UBYTE,
            ),
        )
    }
    return texture
}

private fun PitRig.releaseDisc() {
    val engine = engine ?: return
    if (discRenderable != 0) {
        runCatching { scene?.removeEntity(discRenderable) }
        runCatching { engine.getRenderableManager().destroy(discRenderable) }
        runCatching { EntityManager.get().destroy(discRenderable) }
    }
    discRenderable = 0
    discBuffers?.let { buffers ->
        runCatching { engine.destroyVertexBuffer(buffers.vertex) }
        runCatching { engine.destroyIndexBuffer(buffers.index) }
    }
    discBuffers = null
    discTexture?.let { runCatching { engine.destroyTexture(it) } }
    discTexture = null
}

private fun clampSampler(): TextureSampler {
    val sampler = TextureSampler(
        TextureSampler.MinFilter.LINEAR_MIPMAP_LINEAR,
        TextureSampler.MagFilter.LINEAR,
        TextureSampler.WrapMode.CLAMP_TO_EDGE,
    )
    sampler.setAnisotropy(ANISOTROPY)
    return sampler
}

private fun tilingSampler(): TextureSampler {
    val sampler = TextureSampler(
        TextureSampler.MinFilter.LINEAR_MIPMAP_LINEAR,
        TextureSampler.MagFilter.LINEAR,
        TextureSampler.WrapMode.REPEAT,
    )
    sampler.setAnisotropy(ANISOTROPY)
    return sampler
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
