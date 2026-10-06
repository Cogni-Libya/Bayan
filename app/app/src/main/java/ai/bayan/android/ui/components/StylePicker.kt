package ai.bayan.android.ui.components

import android.os.Build
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.semantics.Role
import androidx.compose.foundation.selection.selectable
import androidx.compose.ui.unit.sp
import ai.bayan.android.R
import ai.bayan.android.data.AppStyle
import ai.bayan.android.ui.theme.BayanDark
import ai.bayan.android.ui.theme.BayanLight
import ai.bayan.android.ui.theme.FallbackDark
import ai.bayan.android.ui.theme.FallbackLight
import ai.bayan.android.ui.theme.ReadexPro

/**
 * The choice between Bayan's own look and the phone's: two cards side by side, each a small preview drawn in that
 * look's own colours and typeface (whatever the current look is), as Android's wallpaper-style picker does.
 */
@Composable
fun StylePicker(selected: AppStyle, dark: Boolean, onSelect: (AppStyle) -> Unit, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        AppStyle.entries.forEach { style ->
            StyleCard(style, style == selected, dark, Modifier.weight(1f)) { onSelect(style) }
        }
    }
}

@Composable
private fun StyleCard(style: AppStyle, selected: Boolean, dark: Boolean, modifier: Modifier, onClick: () -> Unit) {
    val scheme = previewScheme(style, dark)
    val font = if (style == AppStyle.Bayan) ReadexPro else FontFamily.Default
    val ring by animateDpAsState(if (selected) 3.dp else 1.dp, spring(stiffness = Spring.StiffnessMediumLow), label = "ring")
    val lift by animateFloatAsState(if (selected) 1f else 0.96f, spring(dampingRatio = 0.6f, stiffness = Spring.StiffnessMediumLow), label = "lift")
    // The whole option is one target (card, name and description), read as one radio button.
    Column(
        modifier
            .clip(RoundedCornerShape(24.dp))
            .selectable(selected = selected, role = Role.RadioButton, onClick = onClick)
            .padding(bottom = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Surface(
            shape = RoundedCornerShape(24.dp),
            color = scheme.surface,
            border = BorderStroke(ring, if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant),
            modifier = Modifier.fillMaxWidth().aspectRatio(0.82f).graphicsLayer { scaleX = lift; scaleY = lift },
        ) {
            // The preview shows Bayan in Arabic, so it is laid out right to left whatever the app's language.
            CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                // the accent, as the sun of the logo
                Box(Modifier.size(22.dp).clip(CircleShape).background(scheme.primary))
                Spacer(Modifier.height(2.dp))
                Text("بيان", fontFamily = font, fontWeight = FontWeight.Medium, fontSize = 22.sp, color = scheme.onSurface, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Start)
                Text("قراءة أسهل", fontFamily = font, fontSize = 14.sp, color = scheme.onSurfaceVariant, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Start)
                Spacer(Modifier.weight(1f))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(width = 52.dp, height = 22.dp).clip(CircleShape).background(scheme.primaryContainer))
                    Spacer(Modifier.width(6.dp))
                    Box(Modifier.size(22.dp).clip(CircleShape).background(scheme.tertiaryContainer))
                    Spacer(Modifier.weight(1f))
                    Box(Modifier.size(22.dp).clip(CircleShape).background(scheme.secondaryContainer))
                }
            }
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            if (selected) Icon(Icons.Rounded.CheckCircle, null, Modifier.size(18.dp), tint = MaterialTheme.colorScheme.primary)
            Text(
                stringResource(if (style == AppStyle.Bayan) R.string.style_bayan else R.string.style_system),
                style = MaterialTheme.typography.titleSmall,
                color = if (selected) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Text(
            stringResource(if (style == AppStyle.Bayan) R.string.style_bayan_body else R.string.style_system_body),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun previewScheme(style: AppStyle, dark: Boolean): ColorScheme = when {
    style == AppStyle.Bayan -> if (dark) BayanDark else BayanLight
    Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
        val context = LocalContext.current
        if (dark) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
    }
    else -> if (dark) FallbackDark else FallbackLight
}
