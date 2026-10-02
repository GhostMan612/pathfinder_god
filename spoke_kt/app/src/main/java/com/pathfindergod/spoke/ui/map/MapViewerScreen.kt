// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.map

import android.content.Context
import androidx.compose.animation.core.FloatExponentialDecaySpec
import androidx.compose.animation.core.animateDecay
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.Velocity
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.service.ExportService
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pathfindergod.spoke.data.local.MapEntity
import com.pathfindergod.spoke.ui.designsystem.Dimens
import com.pathfindergod.spoke.ui.designsystem.GodBackLink
import com.pathfindergod.spoke.ui.designsystem.GodCard
import com.pathfindergod.spoke.ui.designsystem.GodChip
import com.pathfindergod.spoke.ui.designsystem.GodEmptyState
import com.pathfindergod.spoke.ui.designsystem.GodStatusText
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.designsystem.Spacing
import com.pathfindergod.spoke.ui.designsystem.godRtlText
import com.pathfindergod.spoke.ui.designsystem.godTouchSize
import com.pathfindergod.spoke.ui.theme.GoldAccent
import com.pathfindergod.spoke.ui.theme.TextPrimary
import com.pathfindergod.spoke.ui.theme.TextSecondary
import com.pathfindergod.spoke.ui.viewmodel.MapViewModel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch

const val MIN_ZOOM = 0.5f
const val MAX_ZOOM = 6f

@Composable
fun MapViewerScreen(
    mapId: String,
    viewModel: MapViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val map = state.maps.firstOrNull { it.id == mapId }
    if (map == null) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                GodEmptyState(text = stringResource(R.string.map_lost))
                GodBackLink(
                    text = godRtlText(R.string.map_back, R.string.map_back_rtl),
                    onClick = onBack,
                    testTag = GodTags.heroBack,
                    modifier = Modifier.padding(top = Spacing.md),
                )
            }
        }
    } else {
        MapCanvas(map = map, onBack = onBack)
    }
}

@Composable
private fun MapCanvas(
    map: MapEntity,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val view = LocalView.current
    val scope = rememberCoroutineScope()
    var gmLayer by rememberSaveable { mutableStateOf(true) }
    var scale by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    val zoomInLabel = stringResource(R.string.a11y_map_zoom_in)
    val zoomOutLabel = stringResource(R.string.a11y_map_zoom_out)
    val zoomResetLabel = stringResource(R.string.a11y_map_zoom_reset)
    val zoomLabel = stringResource(R.string.a11y_map_zoom, (scale * 100f).toInt())
    val zoomActions = listOf(
        CustomAccessibilityAction(zoomInLabel) {
            scale = (scale * 1.5f).coerceIn(MIN_ZOOM, MAX_ZOOM)
            view.announceForAccessibility(zoomPercentAnnouncement(context, scale))
            true
        },
        CustomAccessibilityAction(zoomOutLabel) {
            scale = (scale / 1.5f).coerceIn(MIN_ZOOM, MAX_ZOOM)
            view.announceForAccessibility(zoomPercentAnnouncement(context, scale))
            true
        },
        CustomAccessibilityAction(zoomResetLabel) {
            scale = 1f
            offset = Offset.Zero
            view.announceForAccessibility(zoomPercentAnnouncement(context, scale))
            true
        },
    )
    val decoded by produceState<ImageBitmap?>(initialValue = null, map.id, gmLayer) {
        value = MapImageDecoder.decode(
            if (gmLayer) map.gmBase64Png else map.playerBase64Png,
            VIEWER_PX,
        )
    }
    val bitmap = decoded
    Column(modifier = Modifier.fillMaxSize().padding(Spacing.lg)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            GodBackLink(
                text = godRtlText(R.string.map_back, R.string.map_back_rtl),
                onClick = onBack,
                testTag = GodTags.heroBack,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(Spacing.md)) {
                GodChip(
                    label = stringResource(R.string.map_layer_gm),
                    selected = gmLayer,
                    onClick = { gmLayer = true },
                    testTag = GodTags.MAP_LAYER_GM,
                )
                GodChip(
                    label = stringResource(R.string.map_layer_player),
                    selected = !gmLayer,
                    onClick = { gmLayer = false },
                    testTag = GodTags.MAP_LAYER_PLAYER,
                )
            }
            Icon(
                imageVector = Icons.Filled.Share,
                contentDescription = stringResource(R.string.map_share),
                tint = GoldAccent,
                modifier = Modifier
                    .clickable(
                        onClickLabel = stringResource(R.string.a11y_map_share),
                        role = Role.Button,
                    ) {
                        ExportService.shareMapImage(
                            context,
                            if (gmLayer) map.gmBase64Png else map.playerBase64Png,
                            map.prompt,
                        )
                    }
                    .godTouchSize()
                    .padding(Spacing.xs)
                    .testTag(GodTags.MAP_SHARE),
            )
        }
        Text(
            text = map.prompt,
            style = MaterialTheme.typography.titleMedium,
            color = TextPrimary,
            modifier = Modifier.padding(top = Spacing.xs),
        )
        GodCard(
            modifier = Modifier.fillMaxWidth().weight(1f).padding(top = Spacing.md),
            contentPadding = PaddingValues(Dimens.gridSpacing),
        ) {
            BoxWithConstraints(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center,
            ) {
                val density = LocalDensity.current
                val viewportWidth = with(density) { maxWidth.toPx() }
                val viewportHeight = with(density) { maxHeight.toPx() }
                val clamp: (Offset) -> Offset = { raw ->
                    val clamped = mapBoundsClamp(
                        offsetX = raw.x,
                        offsetY = raw.y,
                        viewportWidth = viewportWidth,
                        viewportHeight = viewportHeight,
                        scale = scale,
                    )
                    Offset(clamped[0], clamped[1])
                }
                if (bitmap != null) {
                    Image(
                        bitmap = bitmap,
                        contentDescription = null,
                        modifier = Modifier
                            .fillMaxSize()
                            .semantics {
                                contentDescription = map.prompt
                                stateDescription = zoomLabel
                                customActions = zoomActions
                            }
                            .testTag(GodTags.MAP_CANVAS)
                            // One gesture detector, not two.
                            //
                            // detectTransformGestures and detectDragGestures
                            // were both attached to this node. Whichever crossed
                            // touch slop first consumed the change, which
                            // cancelled the other: a fast flick gave panning but
                            // left the velocity tracker empty, so the entire
                            // animateDecay fling block was unreachable and the
                            // map had no inertia; a slow drag let the transform
                            // detector see canceled=true and park, so pinch-zoom
                            // did not register for that gesture either.
                            //
                            // The fling never fired even once, so folding the
                            // pan/zoom into a single detector is not a
                            // regression: it makes pinch and panning reliable
                            // on every gesture.
                            .pointerInput(Unit) {
                                detectTransformGestures(panZoomLock = true) { _, pan, zoom, _ ->
                                    scale = (scale * zoom).coerceIn(MIN_ZOOM, MAX_ZOOM)
                                    offset = clamp(offset + pan)
                                }
                            }
                            .graphicsLayer(
                                scaleX = scale,
                                scaleY = scale,
                                translationX = offset.x,
                                translationY = offset.y,
                            ),
                    )
                } else {
                    GodStatusText(text = stringResource(R.string.map_unresolved))
                }
            }
        }
    }
}

private fun zoomPercentAnnouncement(context: Context, scale: Float): String =
    context.getString(R.string.a11y_map_zoom, (scale * 100f).toInt())
