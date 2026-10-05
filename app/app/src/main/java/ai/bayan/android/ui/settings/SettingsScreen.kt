package ai.bayan.android.ui.settings

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings as SystemSettings
import androidx.annotation.StringRes
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.DarkMode
import androidx.compose.material.icons.rounded.FontDownload
import androidx.compose.material.icons.rounded.FormatLineSpacing
import androidx.compose.material.icons.rounded.Highlight
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Language
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.Memory
import androidx.compose.material.icons.rounded.RecordVoiceOver
import androidx.compose.material.icons.rounded.RestartAlt
import androidx.compose.material.icons.rounded.SpaceBar
import androidx.compose.material.icons.rounded.Speed
import androidx.compose.material.icons.rounded.TextFields
import androidx.compose.material.icons.rounded.Texture
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.Icon
import androidx.compose.material3.LargeFlexibleTopAppBar
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.ListItemShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedListItem
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberTopAppBarState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import ai.bayan.android.AppContainer
import ai.bayan.android.BuildConfig
import ai.bayan.android.R
import ai.bayan.android.data.ReaderFont
import ai.bayan.android.data.ReaderStyle
import ai.bayan.android.data.ReaderSurface
import ai.bayan.android.data.ThemeMode
import ai.bayan.android.ui.theme.isDark
import ai.bayan.android.ui.components.StylePicker
import ai.bayan.android.data.AppStyle
import ai.bayan.android.model.ModelCatalog
import ai.bayan.android.speech.VoiceCatalog
import ai.bayan.android.ui.appViewModel
import ai.bayan.android.ui.components.ReaderText
import ai.bayan.android.ui.components.SectionHeader
import ai.bayan.android.ui.theme.colors
import kotlin.math.roundToInt
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class SettingsViewModel(private val app: AppContainer) : ViewModel() {
    private val repo = app.settings
    val settings = repo.settings.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    private fun set(block: suspend () -> Unit) { viewModelScope.launch { block() } }
    fun font(v: ReaderFont) = set { repo.setReaderFont(v) }
    fun size(v: Float) = set { repo.setReaderSize(v) }
    fun lineHeight(v: Float) = set { repo.setLineHeight(v) }
    fun wordSpacing(v: Float) = set { repo.setWordSpacing(v) }
    fun surface(v: ReaderSurface) = set { repo.setSurface(v) }
    fun speechRate(v: Float) = set { repo.setSpeechRate(v) }
    fun highlight(v: Boolean) = set { repo.setHighlight(v) }
    fun moreFaithful(v: Boolean) = set { repo.setMoreFaithful(v) }
    fun theme(v: ThemeMode) = set { repo.setThemeMode(v) }
    fun style(v: AppStyle) = set { repo.setStyle(v) }
    fun resetReader() = set {
        val d = ReaderStyle()
        repo.setReaderFont(d.font); repo.setReaderSize(d.sizeSp); repo.setLineHeight(d.lineHeight)
        repo.setWordSpacing(d.wordSpacing); repo.setSurface(d.surface)
    }
    fun previewSpeech(text: String, rate: Float) = app.readAloud.speak("settings-preview", text, rate)
}

private enum class Choice { None, Font, Theme }

@OptIn(ExperimentalMaterial3Api::class, ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun SettingsScreen(onOpenModels: () -> Unit, onOpenVoices: () -> Unit, vm: SettingsViewModel = appViewModel { SettingsViewModel(it) }) {
    val loaded by vm.settings.collectAsStateWithLifecycle()
    val settings = loaded ?: return
    val context = LocalContext.current
    val appBar = TopAppBarDefaults.exitUntilCollapsedScrollBehavior(rememberTopAppBarState())
    var choice by rememberSaveable { mutableStateOf(Choice.None) }

    // Sliders move the preview live and save when the finger lifts.
    var size by remember(settings.reader.sizeSp) { mutableFloatStateOf(settings.reader.sizeSp) }
    var line by remember(settings.reader.lineHeight) { mutableFloatStateOf(settings.reader.lineHeight) }
    var words by remember(settings.reader.wordSpacing) { mutableFloatStateOf(settings.reader.wordSpacing) }
    var rate by remember(settings.speechRate) { mutableFloatStateOf(settings.speechRate) }
    val preview = settings.reader.copy(sizeSp = size, lineHeight = line, wordSpacing = words)
    val sample = stringResource(R.string.settings_speech_sample)

    Scaffold(
        modifier = Modifier.nestedScroll(appBar.nestedScrollConnection),
        topBar = { LargeFlexibleTopAppBar(title = { Text(stringResource(R.string.nav_settings)) }, scrollBehavior = appBar) },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            Column(
                Modifier.widthIn(max = 720.dp).fillMaxWidth().verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, bottom = 32.dp),
                verticalArrangement = Arrangement.spacedBy(ListItemDefaults.SegmentedGap),
            ) {
                ReaderText(stringResource(R.string.settings_preview_text), preview, Modifier.padding(bottom = 8.dp))

                SectionHeader(stringResource(R.string.settings_section_reading))
                Item(0, 6, Icons.Rounded.FontDownload, R.string.settings_font, stringResource(fontLabel(settings.reader.font)), onClick = { choice = Choice.Font })
                SliderItem(1, 6, Icons.Rounded.TextFields, R.string.settings_size, "${size.roundToInt()}", size, 16f..34f, 8, { size = it }) { vm.size(size) }
                SliderItem(2, 6, Icons.Rounded.FormatLineSpacing, R.string.settings_line_height, "%.1f×".format(line), line, 1.4f..2.4f, 9, { line = it }) { vm.lineHeight(line) }
                SliderItem(
                    3, 6, Icons.Rounded.SpaceBar, R.string.settings_word_spacing,
                    if (words < 0.01f) stringResource(R.string.spacing_normal) else stringResource(R.string.spacing_wider, (words * 100).roundToInt()),
                    words, 0f..0.3f, 9, { words = it },
                ) { vm.wordSpacing(words) }
                SegmentedListItem(
                    shapes = shapes(4, 6),
                    leadingContent = { Icon(Icons.Rounded.Texture, null) },
                    supportingContent = { SurfacePicker(settings.reader.surface, vm::surface) },
                ) { Text(stringResource(R.string.settings_surface)) }
                Item(5, 6, Icons.Rounded.RestartAlt, R.string.settings_reset_reading, null, onClick = vm::resetReader)

                SectionHeader(stringResource(R.string.settings_section_listening))
                SliderItem(0, 3, Icons.Rounded.Speed, R.string.settings_speech_rate, "%.1f×".format(rate), rate, 0.5f..1.5f, 9, { rate = it }) {
                    vm.speechRate(rate)
                    vm.previewSpeech(sample, rate)
                }
                SegmentedListItem(
                    checked = settings.highlightWhileReading,
                    onCheckedChange = vm::highlight,
                    shapes = shapes(1, 3),
                    leadingContent = { Icon(Icons.Rounded.Highlight, null) },
                    supportingContent = { Text(stringResource(R.string.settings_highlight_body)) },
                    trailingContent = { Switch(checked = settings.highlightWhileReading, onCheckedChange = null) },
                ) { Text(stringResource(R.string.settings_highlight)) }
                Item(2, 3, Icons.Rounded.RecordVoiceOver, R.string.voices_title, stringResource(VoiceCatalog.get(settings.voice).title), onClick = onOpenVoices)

                SectionHeader(stringResource(R.string.settings_section_model))
                // The "more faithful" switch only for models whose beam search was benchmarked (ModelInfo.beams).
                val offersBeams = ModelCatalog.get(settings.activeModel).beams > 1
                Item(0, if (offersBeams) 2 else 1, Icons.Rounded.Memory, R.string.settings_model, stringResource(ModelCatalog.get(settings.activeModel).title), onClick = onOpenModels)
                if (offersBeams) SegmentedListItem(
                    checked = settings.moreFaithful,
                    onCheckedChange = vm::moreFaithful,
                    shapes = shapes(1, 2),
                    leadingContent = { Icon(Icons.Rounded.Verified, null) },
                    supportingContent = { Text(stringResource(R.string.settings_more_faithful_body)) },
                    trailingContent = { Switch(checked = settings.moreFaithful, onCheckedChange = null) },
                ) { Text(stringResource(R.string.settings_more_faithful)) }

                SectionHeader(stringResource(R.string.settings_section_appearance))
                StylePicker(
                    settings.style, settings.themeMode.isDark(), onSelect = { vm.style(it) },
                    Modifier.padding(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 16.dp),
                )
                val languages = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                val count = if (languages) 2 else 1
                Item(0, count, Icons.Rounded.DarkMode, R.string.settings_theme, stringResource(themeLabel(settings.themeMode)), onClick = { choice = Choice.Theme })
                if (languages) {
                    Item(1, count, Icons.Rounded.Language, R.string.settings_language, currentLanguage(), onClick = {
                        context.startActivity(Intent(SystemSettings.ACTION_APP_LOCALE_SETTINGS, Uri.fromParts("package", context.packageName, null)))
                    })
                }

                SectionHeader(stringResource(R.string.settings_section_about))
                Item(0, 3, Icons.Rounded.Lock, R.string.settings_privacy, stringResource(R.string.settings_privacy_body))
                Item(1, 3, Icons.Rounded.Info, R.string.settings_version_title, BuildConfig.VERSION_NAME)
                Item(2, 3, Icons.Rounded.FontDownload, R.string.settings_fonts, stringResource(R.string.settings_fonts_body))
            }
        }
    }

    when (choice) {
        Choice.Font -> RadioDialog(
            title = R.string.settings_font,
            options = ReaderFont.entries.map { fontLabel(it) },
            selected = settings.reader.font.ordinal,
            onSelect = { vm.font(ReaderFont.entries[it]) },
            onDismiss = { choice = Choice.None },
        )
        Choice.Theme -> RadioDialog(
            title = R.string.settings_theme,
            options = ThemeMode.entries.map { themeLabel(it) },
            selected = settings.themeMode.ordinal,
            onSelect = { vm.theme(ThemeMode.entries[it]) },
            onDismiss = { choice = Choice.None },
        )
        Choice.None -> Unit
    }
}

@StringRes private fun fontLabel(f: ReaderFont) = when (f) {
    ReaderFont.Readex -> R.string.font_readex
    ReaderFont.Naskh -> R.string.font_naskh
    ReaderFont.System -> R.string.font_system
}

/** The app's language as it is now, named in itself (Android 13+ per-app languages). */
@Composable
private fun currentLanguage(): String {
    val context = LocalContext.current
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return stringResource(R.string.settings_language_body)
    val chosen = context.getSystemService(android.app.LocaleManager::class.java).applicationLocales
    return if (chosen.isEmpty) {
        val phone = java.util.Locale.getDefault()
        stringResource(R.string.language_follows_phone, phone.getDisplayLanguage(phone))
    } else chosen[0].let { it.getDisplayLanguage(it) }
}

@StringRes private fun themeLabel(m: ThemeMode) = when (m) {
    ThemeMode.System -> R.string.theme_system
    ThemeMode.Light -> R.string.theme_light
    ThemeMode.Dark -> R.string.theme_dark
}

@StringRes private fun surfaceLabel(s: ReaderSurface) = when (s) {
    ReaderSurface.Default -> R.string.surface_default
    ReaderSurface.Cream -> R.string.surface_cream
    ReaderSurface.Mint -> R.string.surface_mint
    ReaderSurface.Paper -> R.string.surface_paper
    ReaderSurface.Night -> R.string.surface_night
}

@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
private fun shapes(index: Int, count: Int): ListItemShapes = ListItemDefaults.segmentedShapes(index, count)

@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
private fun Item(index: Int, count: Int, icon: ImageVector, @StringRes title: Int, summary: String?, onClick: (() -> Unit)? = null) {
    val summaryContent: (@Composable () -> Unit)? = summary?.let { { Text(it) } }
    if (onClick != null) {
        SegmentedListItem(
            onClick = onClick,
            shapes = shapes(index, count),
            leadingContent = { Icon(icon, null) },
            supportingContent = summaryContent,
        ) { Text(stringResource(title)) }
    } else {
        SegmentedListItem(
            shapes = shapes(index, count),
            leadingContent = { Icon(icon, null) },
            supportingContent = summaryContent,
        ) { Text(stringResource(title)) }
    }
}

@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
private fun SliderItem(
    index: Int,
    count: Int,
    icon: ImageVector,
    @StringRes title: Int,
    valueLabel: String,
    value: Float,
    range: ClosedFloatingPointRange<Float>,
    steps: Int,
    onChange: (Float) -> Unit,
    onCommit: () -> Unit,
) {
    val haptics = LocalHapticFeedback.current
    SegmentedListItem(
        shapes = shapes(index, count),
        leadingContent = { Icon(icon, null) },
        trailingContent = { Text(valueLabel, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary) },
        supportingContent = {
            Slider(
                value = value,
                onValueChange = { if (it != value) haptics.performHapticFeedback(HapticFeedbackType.SegmentFrequentTick); onChange(it) },
                valueRange = range,
                steps = steps,
                onValueChangeFinished = onCommit,
            )
        },
    ) { Text(stringResource(title)) }
}

@Composable
private fun SurfacePicker(current: ReaderSurface, onSelect: (ReaderSurface) -> Unit) {
    val haptics = LocalHapticFeedback.current
    Row(Modifier.fillMaxWidth().padding(top = 12.dp).selectableGroup(), horizontalArrangement = Arrangement.SpaceBetween) {
        ReaderSurface.entries.forEach { s ->
            val selected = current == s
            val c = s.colors()
            Column(
                Modifier.selectable(selected, role = Role.RadioButton) { haptics.performHapticFeedback(HapticFeedbackType.SegmentTick); onSelect(s) },
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Surface(
                    color = c.background,
                    shape = CircleShape,
                    modifier = Modifier.size(48.dp).border(
                        if (selected) 3.dp else 1.dp,
                        if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant,
                        CircleShape,
                    ),
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        if (selected) Icon(Icons.Rounded.Check, null, tint = c.text)
                        else Text("أ", color = c.text, style = MaterialTheme.typography.titleMedium)
                    }
                }
                Spacer(Modifier.height(6.dp))
                Text(stringResource(surfaceLabel(s)), style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}

/** A single-choice dialog, as the system uses for settings with a few fixed options. */
@Composable
private fun RadioDialog(@StringRes title: Int, options: List<Int>, selected: Int, onSelect: (Int) -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(title)) },
        text = {
            Column(Modifier.selectableGroup()) {
                options.forEachIndexed { i, label ->
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .height(56.dp)
                            .selectable(i == selected, role = Role.RadioButton) { onSelect(i); onDismiss() },
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(selected = i == selected, onClick = null)
                        Text(stringResource(label), style = MaterialTheme.typography.bodyLarge, modifier = Modifier.padding(start = 16.dp))
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.action_cancel)) } },
    )
}
