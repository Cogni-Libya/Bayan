package ai.bayan.android.ui.process

import android.content.Intent
import android.graphics.Color as AndroidColor
import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.net.Uri
import android.os.Bundle
import androidx.compose.material.icons.rounded.PictureInPictureAlt
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.animate
import androidx.compose.ui.geometry.Offset
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.unit.Velocity
import ai.bayan.android.speech.SpeechState
import ai.bayan.android.ui.theme.colors
import androidx.compose.material.icons.rounded.KeyboardArrowDown
import androidx.compose.material.icons.rounded.KeyboardArrowUp
import androidx.compose.material3.LoadingIndicator
import androidx.compose.material3.LocalContentColor
import androidx.compose.ui.text.style.TextOverflow
import ai.bayan.android.speech.ReadAloud
import ai.bayan.android.speech.ReadingService
import ai.bayan.android.ui.components.FollowReading
import ai.bayan.android.ui.components.ListenIconToggle
import ai.bayan.android.ui.theme.ContentDirection
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.PredictiveBackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import kotlinx.coroutines.delay
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.ui.layout.onSizeChanged
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withTimeoutOrNull
import androidx.lifecycle.lifecycleScope
import androidx.compose.animation.core.FastOutLinearInEasing
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.draw.drawBehind
import androidx.compose.animation.core.LinearOutSlowInEasing
import androidx.compose.ui.util.lerp
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.Density
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.Outline
import androidx.compose.ui.graphics.Paint
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.ErrorOutline
import androidx.compose.material.icons.rounded.SwapHoriz
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.withFrameNanos
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.graphics.drawable.toBitmap
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import ai.bayan.android.AppContainer
import ai.bayan.android.BayanApp
import ai.bayan.android.MainActivity
import ai.bayan.android.R
import ai.bayan.android.data.Settings
import ai.bayan.android.model.ModelCatalog
import ai.bayan.android.ui.SimplifySession
import ai.bayan.android.ui.SimplifyState
import ai.bayan.android.ui.appViewModel
import ai.bayan.android.ui.components.LocalAppContainer
import ai.bayan.android.ui.components.AutoRead
import ai.bayan.android.ui.components.OriginalToggle
import ai.bayan.android.ui.components.ReaderActions
import ai.bayan.android.ui.components.ReaderText
import ai.bayan.android.ui.components.UnchangedNote
import ai.bayan.android.ui.components.isUnchanged
import ai.bayan.android.ui.components.spokenRange
import ai.bayan.android.ui.home.NoticeCard
import ai.bayan.android.ui.isBusy
import ai.bayan.android.ui.theme.BayanTheme
import ai.bayan.android.ui.theme.isDark
import kotlin.coroutines.cancellation.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** "تبسيط" in any app's text-selection menu: simplifies the selection in a panel over that app. */
class ProcessTextActivity : ComponentActivity() {
    /** True once the window has focus, i.e. is on screen: the entrance (panel and light) is timed from it. Compose
     *  draws its first frames before the window is shown, so a clock started at the first frame would run unseen. */
    private val onScreen = kotlinx.coroutines.flow.MutableStateFlow(false)

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) {
            onScreen.value = true
            // Only now (the panel is drawn over it) does the floating pill go, so there is no gap between them.
            (application as BayanApp).container.overlay.setMinimized(false)
        }
    }


    /** The selection being simplified; a new selection while the panel is open replaces it. */
    private val selection = MutableStateFlow("")

    /** The media controls are a notification: ask once (Android 13+), then minimize whatever the answer. */
    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { minimizeNow() }

    /** Asking for "Display over other apps" before the first minimize. */
    private val askFloating = MutableStateFlow(false)
    private val overlaySettings = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { minimizeWithNotifications() }

    private fun minimize() {
        val app = (application as BayanApp).container
        if (!android.provider.Settings.canDrawOverlays(this) && !app.overlay.floatingDeclined) askFloating.value = true
        else minimizeWithNotifications()
    }

    private fun allowFloating() {
        askFloating.value = false
        overlaySettings.launch(Intent(android.provider.Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
    }

    private fun declineFloating() {
        askFloating.value = false
        (application as BayanApp).container.overlay.floatingDeclined = true
        minimizeWithNotifications()
    }

    private fun minimizeWithNotifications() {
        val needsPermission = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        if (needsPermission) notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS) else minimizeNow()
    }

    private fun minimizeNow() {
        val app = (application as BayanApp).container
        app.overlay.setMinimized(true)
        startForegroundService(Intent(this, ReadingService::class.java))
        // Stay (as the pill, showing what the floating pill shows) until the floating pill is drawn over us, then go
        // without a transition.
        lifecycleScope.launch {
            withTimeoutOrNull(900) { app.overlay.floatingShown.first { it } }
            delay(48)
            finish()
            overridePendingTransition(0, 0)
        }
    }
    private var readOnly = true

    private fun receive(intent: Intent): Boolean {
        val app = (application as BayanApp).container
        if (intent.action == ACTION_RESUME) {
            // Reopened from the media controls: show the selection that is being read.
            readOnly = true
            selection.value = app.overlay.text ?: return false
            return true
        }
        val text = intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)?.toString().orEmpty()
        if (text.isBlank()) return false
        readOnly = intent.getBooleanExtra(Intent.EXTRA_PROCESS_TEXT_READONLY, true)
        selection.value = text
        return true
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        receive(intent)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = (application as BayanApp).container
        if (!receive(intent)) { finish(); return }
        val resumed = intent.action == ACTION_RESUME
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.auto(AndroidColor.TRANSPARENT, AndroidColor.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.auto(AndroidColor.TRANSPARENT, AndroidColor.TRANSPARENT),
        )

        setContent {
            val text by selection.collectAsStateWithLifecycle()
            val settings by app.settings.settings.collectAsStateWithLifecycle(null)
            val s = settings ?: return@setContent
            val dark = s.themeMode.isDark()
            DisposableEffect(dark) {
                val style = SystemBarStyle.auto(AndroidColor.TRANSPARENT, AndroidColor.TRANSPARENT) { dark }
                enableEdgeToEdge(statusBarStyle = style, navigationBarStyle = style)
                onDispose {}
            }
            CompositionLocalProvider(LocalAppContainer provides app) {
                BayanTheme(s.themeMode) {
                    val visible by onScreen.collectAsStateWithLifecycle()
                    ProcessTextOverlay(
                        text = text,
                        onScreen = visible,
                        resumed = resumed,
                        canReplace = !readOnly,
                        onReplace = { result ->
                            setResult(RESULT_OK, Intent().putExtra(Intent.EXTRA_PROCESS_TEXT, result))
                            finish()
                        },
                        onOpenApp = {
                            startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                            finish()
                        },
                        onMinimize = ::minimize,
                        onDismiss = ::finish,
                    )
                    val asking by askFloating.collectAsStateWithLifecycle()
                    if (asking) {
                        AlertDialog(
                            onDismissRequest = ::declineFloating,
                            icon = { Icon(Icons.Rounded.PictureInPictureAlt, null) },
                            title = { Text(stringResource(R.string.floating_title)) },
                            text = { Text(stringResource(R.string.floating_body)) },
                            confirmButton = { TextButton(onClick = ::allowFloating) { Text(stringResource(R.string.floating_allow)) } },
                            dismissButton = { TextButton(onClick = ::declineFloating) { Text(stringResource(R.string.floating_not_now)) } },
                        )
                    }
                }
            }
        }
    }

    override fun onDestroy() {
        val app = (application as BayanApp).container
        // Closed (not minimized): stop reading and forget the selection.
        if (isFinishing && !app.overlay.minimized.value) app.overlay.close()
        super.onDestroy()
    }

    companion object {
        const val ACTION_RESUME = "ai.bayan.android.RESUME_READING"
    }
}

@Composable
private fun ProcessTextOverlay(
    text: String,
    onScreen: Boolean,
    resumed: Boolean,
    canReplace: Boolean,
    onReplace: (String) -> Unit,
    onOpenApp: () -> Unit,
    onMinimize: () -> Unit,
    onDismiss: () -> Unit,
) {
    val app = LocalAppContainer.current
    val overlay = app.overlay
    LaunchedEffect(text) { overlay.open(text) }
    val state by overlay.simplify.state.collectAsStateWithLifecycle()
    val settings by app.settings.settings.collectAsStateWithLifecycle(Settings())
    val scope = rememberCoroutineScope()
    val haptics = LocalHapticFeedback.current
    val density = LocalDensity.current

    // The entrance, after the system assistant's (measured frame by frame): a small droplet of the panel's surface is
    // born on the gesture bar, lifts off it and springs out sideways into a pill; the light blooms as the pill reaches
    // its full width; then the pill unfolds upward into the panel, like a page opening, and the content fades in last.
    // Reopened from the floating pill, it starts as that pill, in its place, and unfolds from it.
    val reveal = remember { Animatable(0f) }
    val enter = remember { Animatable(if (resumed) 1f else 0f) }
    val lift = remember { Animatable(if (resumed) 1f else 0f) }      // the droplet rising off the gesture bar
    val birth = remember { Animatable(if (resumed) 1f else 0f) }     // the droplet stretching into a pill (springs past 1, then settles)
    val unfold = remember { Animatable(0f) }    // the pill opening upward into the panel
    val shownHeight = remember { Animatable(0f) }  // the panel's visible height, gliding after its laid-out height
    var entranceDone by remember { mutableStateOf(false) }
    val halo = remember { Animatable(0f) }      // the light the droplet is born in, before the rim takes over
    var folding by remember { mutableStateOf(false) }
    val contentIn = remember { Animatable(0f) }
    var lightOn by remember { mutableStateOf(false) }
    var closing by remember { mutableStateOf(false) }
    var dragY by remember { mutableFloatStateOf(0f) }
    /** Only a finger moves the panel: the automatic scrolling that follows the spoken word must not. */
    var fingerDown by remember { mutableStateOf(false) }
    var backProgress by remember { mutableFloatStateOf(0f) }
    var panel by remember { mutableStateOf<Rect?>(null) }
    var panelBox by remember { mutableStateOf<Rect?>(null) }   // the panel's laid-out bounds, before its entrance transform
    var showOriginal by rememberSaveable { mutableStateOf(false) }
    val working = state.isBusy || state is SimplifyState.Idle

    // What is being read; the same key the media controls use once the panel is minimized.
    val key = overlay.key(state, showOriginal)
    val readable = when (val st = state) {
        is SimplifyState.Running -> st.partial.take(st.committed)
        is SimplifyState.Done -> if (showOriginal) st.source else st.result
        else -> ""
    }
    val complete = state is SimplifyState.Done
    FollowReading(key, readable, complete, settings.speechRate)
    AutoRead(settings.autoRead, key, readable, settings.speechRate)

    // Timed from the moment the window is on screen (it has no window animation; 1 s at most): the panel springs up and
    // the light rises with it, as the system assistant's do.
    var started by remember { mutableStateOf(false) }
    LaunchedEffect(onScreen) {
        if (!onScreen) delay(1000)
        if (started) return@LaunchedEffect
        withFrameNanos { }
        started = true
        enter.snapTo(1f)
        haptics.performHapticFeedback(HapticFeedbackType.ContextClick)
        launch { reveal.animateTo(1f, tween(450, easing = FastOutSlowInEasing)) }
        if (resumed) {
            lightOn = true
            launch { delay(4200); entranceDone = true }
            launch { unfold.animateTo(1f, spring(dampingRatio = 0.82f, stiffness = 300f)) }
            launch { delay(160); contentIn.animateTo(1f, tween(260, easing = LinearOutSlowInEasing)) }
            return@LaunchedEffect
        }
        launch { lift.animateTo(1f, tween(120, easing = FastOutSlowInEasing)) }
        launch { halo.animateTo(1f, tween(160, easing = LinearOutSlowInEasing)); delay(260); halo.animateTo(0f, tween(650, easing = FastOutSlowInEasing)) }
        launch { delay(80); birth.animateTo(1f, spring(dampingRatio = 0.7f, stiffness = 330f)) }
        launch { delay(300); lightOn = true; delay(4200); entranceDone = true }
        launch { delay(380); unfold.animateTo(1f, spring(dampingRatio = 0.82f, stiffness = 260f)) }
        launch { delay(540); contentIn.animateTo(1f, tween(280, easing = LinearOutSlowInEasing)) }
    }
    LaunchedEffect(state is SimplifyState.Done) {
        if (state is SimplifyState.Done) haptics.performHapticFeedback(HapticFeedbackType.Confirm)
    }
    val close: () -> Unit = {
        if (!closing) {
            closing = true
            folding = true
            // The way it came: the content goes, the panel folds back into the pill and sinks into the gesture bar.
            scope.launch {
                launch { contentIn.animateTo(0f, tween(90)) }
                launch { enter.animateTo(0f, tween(340)) }
                delay(50)
                launch { unfold.animateTo(0f, tween(200, easing = FastOutLinearInEasing)) }
                delay(130)
                birth.animateTo(0f, tween(150, easing = FastOutLinearInEasing))
                lift.animateTo(0f, tween(90))
                onDismiss()
            }
        }
    }
    val springBack: () -> Unit = {
        scope.launch { animate(dragY, 0f, animationSpec = spring(dampingRatio = 0.8f, stiffness = Spring.StiffnessMediumLow)) { v, _ -> dragY = v } }
    }
    /**
     * Back to the app the text came from while Bayan reads on: the panel folds into its pill, where the floating pill
     * takes over (same size, same place). Without the floating pill (not allowed), it sinks into the gesture bar.
     */
    val context = LocalContext.current
    val minimize: () -> Unit = {
        if (!closing) {
            closing = true
            folding = true
            haptics.performHapticFeedback(HapticFeedbackType.SegmentTick)
            val floats = android.provider.Settings.canDrawOverlays(context)
            scope.launch {
                launch { contentIn.animateTo(0f, tween(90)) }
                launch { enter.animateTo(0f, tween(260)) }
                launch { animate(dragY, 0f, animationSpec = tween(420, easing = EmphasizedDecelerate)) { v, _ -> dragY = v } }
                delay(50)
                // Material's emphasized curve: away fast, landing softly on the pill.
                unfold.animateTo(0f, tween(420, easing = EmphasizedDecelerate))
                if (!floats) {
                    birth.animateTo(0f, tween(150, easing = FastOutLinearInEasing))
                    lift.animateTo(0f, tween(90))
                }
                onMinimize()
            }
        }
    }
    PredictiveBackHandler(enabled = !closing) { events ->
        try {
            events.collect { backProgress = it.progress }
            close()
        } catch (e: CancellationException) {
            backProgress = 0f
            throw e
        }
    }

    // While Bayan works the whole screen glows.
    val settle = tween<Float>(1100)
    val quiet = closing
    // The light's entrance always plays to the end, even when the text is ready at once.
    // Once the text is ready the light settles to a faint, still glow (no motion to pull the eye from the text).
    val settled = !working && entranceDone
    val edge by animateFloatAsState(
        if (quiet) 0f else 1f,
        when { quiet -> tween(260) /* gone before the window is */; !settled -> tween(300); else -> settle },
        label = "edge",
    )
    // On Android 13+ the light's own still grain stands in for a scrim; before that, a faint scrim.
    val scrim = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) 0f else 0.06f

    // Dragging anywhere on the panel: it follows the finger and shrinks a little as it goes down.
    // A short pull (or a fling) collapses it to a few lines; a long pull closes it; dragging up expands it again.
    val minimizeAt = with(density) { 72.dp.toPx() }
    val closeAt = with(density) { 260.dp.toPx() }
    val settleDrag: (Float) -> Unit = { velocity ->
        val y = dragY
        when {
            y > closeAt || velocity > 4000f -> close()
            y > minimizeAt || velocity > 1000f -> minimize()
            else -> springBack()
        }
    }
    val dragState = rememberDraggableState { delta ->
        dragY = (dragY + delta).coerceAtLeast(0f)
    }
    // The text scrolls first; once it is at the top, a downward drag moves the panel instead.
    val panelScroll = remember {
        object : NestedScrollConnection {
            override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset {
                if (fingerDown && dragY > 0f && available.y < 0f) {
                    val used = maxOf(available.y, -dragY)
                    dragY += used
                    return Offset(0f, used)
                }
                return Offset.Zero
            }
            override fun onPostScroll(consumed: Offset, available: Offset, source: NestedScrollSource): Offset {
                if (fingerDown && source == NestedScrollSource.UserInput && available.y > 0f) {
                    dragY += available.y
                    return Offset(0f, available.y)
                }
                return Offset.Zero
            }
            override suspend fun onPreFling(available: Velocity): Velocity {
                if (dragY > 0f) { settleDrag(available.y); return available }
                return Velocity.Zero
            }
        }
    }

    val haloColour = edgeLightColours()[0]
    // What the reader sees of the panel right now (droplet, pill or panel), for the light that hugs its outline.
    val litPanel: () -> Rect? = { panelBox?.let { box ->
        with(density) {
            val b = birth.value.coerceAtLeast(0f)
            val u = unfold.value.coerceAtLeast(0f)
            val w = lerp(lerp(64.dp.toPx(), box.width * PILL_FRACTION, b), box.width, u).coerceAtMost(box.width) * (1f + (b - 1f).coerceAtLeast(0f))
            val full = shownHeight.value.takeIf { it > 0f }?.coerceAtMost(box.height) ?: box.height
            val h = lerp(lerp(18.dp.toPx(), PILL_HEIGHT.toPx(), b.coerceIn(0f, 1f)), full, u).coerceAtMost(box.height)
            val bottom = box.bottom + dragY.coerceAtLeast(0f) * 0.85f + (1f - lift.value) * 26.dp.toPx()
            Rect(box.center.x - w / 2f, bottom - h, box.center.x + w / 2f, bottom)
        }
    } }
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val maxPanel = maxHeight * 0.82f
        Box(
            Modifier
                .fillMaxSize()
                .graphicsLayer { alpha = reveal.value.coerceIn(0f, 1f) * (if (closing) enter.value else 1f) }
                .background(MaterialTheme.colorScheme.scrim.copy(alpha = scrim))
                .clickable(
                    interactionSource = remember { MutableInteractionSource() },
                    indication = null,
                    // As with the system assistant, tapping the app behind does not end Bayan: the panel steps aside
                    // to the floating panel and goes on reading while the app is used. With nothing to keep, it closes.
                    onClick = { if (state is SimplifyState.Done || working) minimize() else close() },
                ),
        )
        OverlayGlow(
            started = lightOn,
            edge = { edge },
            veil = { reveal.value.coerceIn(0f, 1f) * (if (closing) enter.value.coerceIn(0f, 1f) else 1f) },
            panel = { if (lift.value > 0f) litPanel() else null },
            working = working,
        )

        Column(
            Modifier
                .align(Alignment.BottomCenter)
                .safeDrawingPadding()
                .imePadding()
                .padding(12.dp)
                .widthIn(max = 640.dp)
                .fillMaxWidth()
                .onGloballyPositioned { panelBox = it.boundsInRoot() }
                .drawBehind {
                    // The droplet's halo: a soft glow of the theme's light under the gesture bar as the droplet is born.
                    val h = halo.value
                    if (h > 0f) {
                        val b = birth.value.coerceIn(0f, 1f)
                        val w = lerp(64.dp.toPx(), size.width * PILL_FRACTION, b)
                        val r = 46.dp.toPx()
                        val c = Offset(size.width / 2f, size.height - 14.dp.toPx() + (1f - lift.value) * 26.dp.toPx())
                        scale(scaleX = (w / 2f + r) / r, scaleY = 1f, pivot = c) {
                            drawCircle(
                                Brush.radialGradient(listOf(haloColour.copy(alpha = 0.75f * h), haloColour.copy(alpha = 0.28f * h), Color.Transparent), c, r),
                                radius = r, center = c,
                            )
                        }
                    }
                }
                .graphicsLayer {
                    val e = if (folding) 1f else enter.value
                    val pull = (dragY / closeAt).coerceIn(0f, 1f)
                    val shrink = (1f - 0.1f * pull) * (1f - 0.08f * backProgress)
                    val b = birth.value
                    val over = (b - 1f).coerceAtLeast(0f)                 // the spring's overshoot stretches it a little
                    transformOrigin = TransformOrigin(0.5f, 1f)
                    translationY = dragY.coerceAtLeast(0f) * 0.85f + (1f - e) * 180.dp.toPx() + (1f - lift.value) * 26.dp.toPx()
                    scaleX = (0.88f + 0.12f * e) * shrink * (1f + over)
                    scaleY = (0.88f + 0.12f * e) * shrink * (1f + 0.5f * over)
                    alpha = e.coerceIn(0f, 1f) * (1f - 0.3f * pull) * (lift.value * 4f).coerceAtMost(1f)
                    val u = unfold.value
                    val visible = shownHeight.value.takeIf { it > 0f } ?: size.height
                    if (b < 1f || u < 1f || visible < size.height - 0.5f) {
                        // a pill of the assistant's proportions (about four fifths of the width), then the panel
                        val pillH = lerp(18.dp.toPx(), PILL_HEIGHT.toPx(), b.coerceIn(0f, 1f))
                        val pillW = lerp(64.dp.toPx(), size.width * PILL_FRACTION, b.coerceAtLeast(0f))
                        clip = true
                        shape = Droplet(lerp(pillW, size.width, u.coerceAtLeast(0f)), lerp(pillH, minOf(visible, size.height), u.coerceAtLeast(0f)), 32.dp.toPx())
                    } else {
                        clip = false
                    }
                }
                .onGloballyPositioned { panel = it.boundsInRoot() }
                .clip(RoundedCornerShape(32.dp))
                .background(MaterialTheme.colorScheme.surfaceContainerLow)
                .drawWithContent {
                    val a = contentIn.value
                    if (a >= 1f) drawContent()
                    else if (a > 0f) drawIntoCanvas { canvas ->
                        canvas.saveLayer(Rect(Offset.Zero, size), Paint().apply { alpha = a })
                        drawContent()
                        canvas.restore()
                    }
                }
                .heightIn(max = maxPanel)
                .pointerInput(Unit) {
                    awaitEachGesture {
                        awaitFirstDown(requireUnconsumed = false, pass = PointerEventPass.Initial)
                        fingerDown = true
                        do {
                            val event = awaitPointerEvent(PointerEventPass.Initial)
                        } while (event.changes.any { it.pressed })
                        fingerDown = false
                    }
                }
                .nestedScroll(panelScroll)
                .draggable(dragState, Orientation.Vertical, onDragStopped = { settleDrag(it) })
                .onSizeChanged { grown ->
                    // The layout takes its new height at once; only the visible edge glides there (a clip, so nothing
                    // is measured again per frame).
                    val h = grown.height.toFloat()
                    scope.launch { if (shownHeight.value <= 0f) shownHeight.snapTo(h) else shownHeight.animateTo(h, spring(dampingRatio = 0.9f, stiffness = 380f)) }
                },
        ) {
            CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onSurface) {
                PanelTopBar(onMinimize = minimize)
                PanelContent(state, settings, key, showOriginal, { showOriginal = it }, canReplace, onReplace, onOpenApp)
            }
        }

        // The pill the panel folds into (and unfolds from), showing what the floating pill shows, so the hand-over
        // between them cannot be seen.
        val pillAlpha = {
            when {
                folding -> ((0.35f - unfold.value) / 0.35f).coerceIn(0f, 1f)
                resumed && !closing -> (1f - unfold.value * 3f).coerceIn(0f, 1f)
                else -> 0f
            }
        }
        // Composed ahead of time (invisible) once the panel is up, so folding never waits for it to be built.
        if (folding || entranceDone || (resumed && !closing)) {
            Box(
                Modifier
                    .align(Alignment.BottomCenter)
                    .safeDrawingPadding()
                    .padding(12.dp)
                    .widthIn(max = 640.dp)
                    .fillMaxWidth()
                    .graphicsLayer {
                        // Hidden (and out of reach of touches) until the panel folds into it.
                        val shown = folding || pillAlpha() > 0f
                        alpha = if (shown) 1f else 0f
                        translationY = if (shown) dragY.coerceAtLeast(0f) * 0.85f else 100_000f
                    },
                contentAlignment = Alignment.BottomCenter,
            ) {
                ReadingPill(
                    onExpand = {}, onClose = close,
                    modifier = Modifier.fillMaxWidth(PILL_FRACTION).height(PILL_HEIGHT),
                    contentAlpha = pillAlpha, elevation = 0.dp,
                )
            }
        }
    }
}

/** The expanded panel's top row: the drag handle, with minimize (⌄) beside it, as on a "Now playing" screen. */
@Composable
private fun PanelTopBar(onMinimize: () -> Unit) {
    Box(Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 2.dp)) {
        IconButton(onClick = onMinimize, modifier = Modifier.align(Alignment.CenterStart)) {
            Icon(Icons.Rounded.KeyboardArrowDown, stringResource(R.string.sheet_minimize))
        }
        Box(
            Modifier
                .align(Alignment.Center)
                .size(width = 32.dp, height = 4.dp)
                .clip(RoundedCornerShape(2.dp))
                .background(MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f)),
        )
    }
}


/**
 * The panel below its handle: the text scrolls on its own, and the controls stay pinned under it however long the
 * selection is. While streaming the view follows the newest words; while reading aloud, the word being spoken.
 */
@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
private fun ColumnScope.PanelContent(
    state: SimplifyState,
    settings: Settings,
    key: String,
    showOriginal: Boolean,
    onShowOriginal: (Boolean) -> Unit,
    canReplace: Boolean,
    onReplace: (String) -> Unit,
    onOpenApp: () -> Unit,
    reveal: Boolean = true,
) {
    val scroll = rememberScrollState()
    val highlight = if (settings.highlightWhileReading) spokenRange(key) else null
    val fade = MaterialTheme.colorScheme.surfaceContainerLow

    Box(Modifier.weight(1f, fill = false)) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(scroll).padding(start = 16.dp, end = 16.dp, bottom = 8.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            when (state) {
                SimplifyState.Idle, SimplifyState.LoadingModel -> ThinkingLines(Modifier.padding(horizontal = 8.dp, vertical = 12.dp))
                is SimplifyState.Running ->
                    if (state.partial.isEmpty()) ThinkingLines(Modifier.padding(horizontal = 8.dp, vertical = 12.dp))
                    else ReaderText(state.partial, settings.reader, highlight = highlight, reveal = reveal, follow = true)
                is SimplifyState.Done -> {
                    ReaderText(
                        if (showOriginal) state.source else state.result,
                        settings.reader,
                        highlight = highlight,
                        reveal = reveal && !showOriginal,
                        follow = highlight != null,
                    )
                    UnchangedNote(state.source, state.result)
                }
                is SimplifyState.NeedsModel -> NoticeCard(
                    icon = Icons.Rounded.Download,
                    title = stringResource(R.string.home_needs_model_title),
                    body = stringResource(R.string.sheet_needs_model_body),
                    action = stringResource(R.string.sheet_open_app),
                    onAction = onOpenApp,
                )
                is SimplifyState.Failed -> NoticeCard(
                    icon = Icons.Rounded.ErrorOutline,
                    title = stringResource(R.string.home_failed_title),
                    body = state.message ?: stringResource(R.string.home_failed_body),
                    error = true,
                )
            }
        }
        // A soft edge where more text continues below the pinned controls.
        if (scroll.canScrollForward) {
            Box(
                Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .height(40.dp)
                    .background(Brush.verticalGradient(listOf(fade.copy(alpha = 0f), fade))),
            )
        }
    }

    // Pinned controls.
    Column(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        when (state) {
            is SimplifyState.Running -> {
                val committed = state.partial.take(state.committed)
                if (committed.isNotEmpty()) ReaderActions(committed, key, settings.speechRate, complete = false)
            }
            is SimplifyState.Done -> {
                // Nothing to compare or replace when Bayan left the text as it was.
                val unchanged = isUnchanged(state.source, state.result)
                if (!unchanged) OriginalToggle(showOriginal, onShowOriginal, Modifier.fillMaxWidth())
                ReaderActions(if (showOriginal) state.source else state.result, key, settings.speechRate)
                if (canReplace && !unchanged) {
                    Button(onClick = { onReplace(state.result) }, shapes = ButtonDefaults.shapes(), modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Rounded.SwapHoriz, null, Modifier.size(ButtonDefaults.IconSize))
                        Spacer(Modifier.width(ButtonDefaults.IconSpacing))
                        Text(stringResource(R.string.sheet_replace))
                    }
                }
            }
            else -> Unit
        }
    }
}

/** The panel while it is being born: a rounded shape of [width] × [height] centred on its bottom edge. */
private class Droplet(private val width: Float, private val height: Float, private val corner: Float) : Shape {
    override fun createOutline(size: Size, layoutDirection: LayoutDirection, density: Density): Outline {
        val w = width.coerceAtMost(size.width)
        val h = height.coerceAtMost(size.height)
        val r = minOf(corner, h / 2f, w / 2f)
        return Outline.Rounded(RoundRect((size.width - w) / 2f, size.height - h, (size.width + w) / 2f, size.height, CornerRadius(r)))
    }
}

/** Material 3's emphasized decelerate curve: quick to leave, very soft to arrive. */
private val EmphasizedDecelerate = CubicBezierEasing(0.05f, 0.7f, 0.1f, 1f)
