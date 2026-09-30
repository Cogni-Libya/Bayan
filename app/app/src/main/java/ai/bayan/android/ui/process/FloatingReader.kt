package ai.bayan.android.ui.process

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.OpenInFull
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.bayan.android.AppContainer
import ai.bayan.android.R
import ai.bayan.android.data.Settings
import ai.bayan.android.ui.SimplifyState
import ai.bayan.android.ui.components.ListenIconToggle
import ai.bayan.android.ui.components.LocalAppContainer
import ai.bayan.android.ui.components.ReaderText
import ai.bayan.android.ui.components.spokenRange
import ai.bayan.android.ui.theme.BayanTheme

/**
 * The minimized "تبسيط" panel, floating over the app the text came from: a few lines that follow the reading,
 * listen / stop, expand back to the full panel, and close. Its handle moves it up or down the screen.
 */
@Composable
fun FloatingReader(container: AppContainer, move: (Float) -> Unit, onExpand: () -> Unit, onClose: () -> Unit) {
    val settings by container.settings.settings.collectAsStateWithLifecycle(Settings())
    val state by container.overlay.simplify.state.collectAsStateWithLifecycle()
    CompositionLocalProvider(LocalAppContainer provides container) {
        BayanTheme(settings.themeMode) {
            val key = container.overlay.key(state)
            val (shown, readable, complete) = when (val st = state) {
                is SimplifyState.Running -> Triple(st.partial, st.partial.take(st.committed), false)
                is SimplifyState.Done -> Triple(st.result, st.result, true)
                else -> Triple("", "", false)
            }
            val highlight = if (settings.highlightWhileReading) spokenRange(key) else null
            Surface(
                color = MaterialTheme.colorScheme.surfaceContainerLow,
                shape = RoundedCornerShape(28.dp),
                shadowElevation = 8.dp,
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp).widthIn(max = 640.dp).fillMaxWidth(),
            ) {
                CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onSurface) {
                    Column {
                        // The handle moves the panel, so it can sit wherever it covers the least.
                        Box(
                            Modifier
                                .fillMaxWidth()
                                .pointerInput(Unit) { detectVerticalDragGestures { change, dy -> change.consume(); move(dy) } }
                                .padding(vertical = 10.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            Box(Modifier.size(width = 32.dp, height = 4.dp).clip(RoundedCornerShape(2.dp)).background(MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f)))
                        }
                        Box(
                            Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 12.dp)
                                .heightIn(max = 116.dp)
                                .clip(MaterialTheme.shapes.extraLarge)
                                .clickable(onClick = onExpand)
                                .verticalScroll(rememberScrollState(), enabled = false),
                        ) {
                            if (shown.isEmpty()) ThinkingLines(Modifier.padding(12.dp), lines = 2)
                            else ReaderText(shown, settings.reader.copy(sizeSp = minOf(settings.reader.sizeSp, 20f)), highlight = highlight, follow = true)
                        }
                        Row(
                            Modifier.fillMaxWidth().padding(start = 12.dp, end = 4.dp, top = 4.dp, bottom = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            ListenIconToggle(readable, key, settings.speechRate, complete)
                            Spacer(Modifier.weight(1f))
                            IconButton(onClick = onExpand) { Icon(Icons.Rounded.OpenInFull, stringResource(R.string.sheet_expand)) }
                            IconButton(onClick = onClose) { Icon(Icons.Rounded.Close, stringResource(R.string.action_close)) }
                        }
                    }
                }
            }
        }
    }
}
