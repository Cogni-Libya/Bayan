package ai.bayan.android.ui.onboarding

import ai.bayan.android.ui.components.LogoLockup
import ai.bayan.android.ui.components.BayanLogo
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.pager.HorizontalPager
import ai.bayan.android.ui.theme.isDark
import ai.bayan.android.ui.components.LocalAppContainer
import ai.bayan.android.ui.components.StylePicker
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.toShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.bayan.android.R
import ai.bayan.android.data.ReaderStyle
import ai.bayan.android.ui.appViewModel
import ai.bayan.android.ui.components.ReaderText
import ai.bayan.android.ui.models.ModelList
import ai.bayan.android.ui.models.ModelsViewModel
import ai.bayan.android.ui.theme.ContentDirection
import kotlinx.coroutines.launch

private const val PAGES = 4

@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun OnboardingScreen(onFinish: () -> Unit, vm: ModelsViewModel = appViewModel { ModelsViewModel(it) }) {
    val pager = rememberPagerState { PAGES }
    val scope = rememberCoroutineScope()
    val last = pager.currentPage == PAGES - 1

    Surface(color = MaterialTheme.colorScheme.surface) {
        Column(Modifier.fillMaxSize().safeDrawingPadding()) {
            HorizontalPager(pager, Modifier.weight(1f), verticalAlignment = Alignment.Top) { page ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
                    Column(
                        Modifier.widthIn(max = 560.dp).fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp, vertical = 24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        when (page) {
                            0 -> WelcomePage()
                            1 -> StylePage()
                            2 -> AnywherePage()
                            else -> ModelPage(vm)
                        }
                    }
                }
            }
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.weight(1f)) {
                    if (!last) TextButton(onClick = onFinish) { Text(stringResource(R.string.onboarding_skip)) }
                }
                PageDots(pager.currentPage, PAGES)
                Box(Modifier.weight(1f), contentAlignment = Alignment.CenterEnd) {
                    Button(
                        onClick = { if (last) onFinish() else scope.launch { pager.animateScrollToPage(pager.currentPage + 1) } },
                        shapes = ButtonDefaults.shapes(),
                    ) { Text(stringResource(if (last) R.string.onboarding_start else R.string.onboarding_next)) }
                }
            }
        }
    }
}

@Composable
private fun PageTitle(title: String, body: String) {
    Text(
        title,
        style = MaterialTheme.typography.headlineLarge,
        textAlign = TextAlign.Center,
        modifier = Modifier.padding(top = 32.dp, bottom = 12.dp).semantics { heading() },
    )
    Text(body, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
}

@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
private fun WelcomePage() {
    // The stacked logo (book and بيان), with its clear space: the sun's diameter all round.
    BayanLogo(LogoLockup.Stacked, Modifier.padding(top = 24.dp).height(112.dp), sunrise = true)
    PageTitle(stringResource(R.string.onboarding_welcome_title), stringResource(R.string.onboarding_welcome_body))
    Spacer(Modifier.height(24.dp))
    Column(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        Text(stringResource(R.string.result_original), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            stringResource(R.string.onboarding_example_before),
            style = MaterialTheme.typography.bodyMedium.merge(ContentDirection),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.fillMaxWidth().clip(MaterialTheme.shapes.large).background(MaterialTheme.colorScheme.surfaceContainer).padding(16.dp),
        )
        Text(stringResource(R.string.result_simplified), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 8.dp))
        ReaderText(stringResource(R.string.onboarding_example_after), ReaderStyle(sizeSp = 20f))
    }
}

/** Bayan's own look or the phone's, chosen once here and changeable in Settings; the screen takes it on at once. */
@Composable
private fun StylePage() {
    val app = LocalAppContainer.current
    val settings by app.settings.settings.collectAsStateWithLifecycle(null)
    val scope = rememberCoroutineScope()
    PageTitle(stringResource(R.string.onboarding_style_title), stringResource(R.string.onboarding_style_body))
    val s = settings ?: return
    StylePicker(s.style, s.themeMode.isDark(), onSelect = { scope.launch { app.settings.setStyle(it) } }, Modifier.padding(top = 8.dp))
}

@Composable
private fun AnywherePage() {
    Spacer(Modifier.height(24.dp))
    // A sketch of Android's text-selection toolbar with Bayan's action in it.
    Surface(shape = RoundedCornerShape(28.dp), color = MaterialTheme.colorScheme.surfaceContainerHighest, shadowElevation = 3.dp) {
        Row(Modifier.padding(6.dp), verticalAlignment = Alignment.CenterVertically) {
            ToolbarItem(stringResource(R.string.onboarding_toolbar_copy), false)
            ToolbarItem(stringResource(R.string.onboarding_toolbar_select_all), false)
            ToolbarItem(stringResource(R.string.process_text_label), true)
        }
    }
    Spacer(Modifier.height(12.dp))
    Text(
        stringResource(R.string.onboarding_example_before),
        style = MaterialTheme.typography.bodyLarge.merge(ContentDirection),
        modifier = Modifier
            .clip(MaterialTheme.shapes.small)
            .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.2f))
            .padding(horizontal = 8.dp, vertical = 4.dp),
    )
    PageTitle(stringResource(R.string.onboarding_anywhere_title), stringResource(R.string.onboarding_anywhere_body))
}

@Composable
private fun ToolbarItem(text: String, highlighted: Boolean) {
    Row(
        Modifier
            .clip(RoundedCornerShape(22.dp))
            .background(if (highlighted) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceContainerHighest)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (highlighted) {
            Icon(Icons.Rounded.AutoAwesome, null, Modifier.size(18.dp), tint = MaterialTheme.colorScheme.onPrimaryContainer)
            Spacer(Modifier.width(6.dp))
        }
        Text(
            text,
            style = MaterialTheme.typography.labelLarge,
            color = if (highlighted) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurface,
        )
    }
}

@Composable
private fun ModelPage(vm: ModelsViewModel) {
    PageTitle(stringResource(R.string.onboarding_model_title), stringResource(R.string.onboarding_model_body))
    Spacer(Modifier.height(8.dp))
    ModelList(vm)
}

@Composable
private fun PageDots(current: Int, count: Int) {
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
        repeat(count) { i ->
            val width by animateDpAsState(if (i == current) 20.dp else 6.dp, MaterialTheme.motionScheme.fastSpatialSpec(), label = "dot")
            val color by animateColorAsState(
                if (i == current) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant,
                label = "dot-color",
            )
            Box(Modifier.height(6.dp).width(width).clip(CircleShape).background(color))
        }
    }
}

