package ai.bayan.android.ui.navigation

import androidx.activity.compose.BackHandler
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.History
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.adaptive.currentWindowAdaptiveInfo
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteItem
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteScaffold
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteScaffoldDefaults
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteType
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.viewmodel.navigation3.rememberViewModelStoreNavEntryDecorator
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey
import androidx.navigation3.runtime.entryProvider
import androidx.navigation3.runtime.rememberNavBackStack
import androidx.navigation3.runtime.rememberSaveableStateHolderNavEntryDecorator
import androidx.navigation3.ui.NavDisplay
import ai.bayan.android.R
import ai.bayan.android.ui.history.HistoryDetailScreen
import ai.bayan.android.ui.history.HistoryScreen
import ai.bayan.android.ui.home.HomeScreen
import ai.bayan.android.ui.models.ModelsScreen
import ai.bayan.android.ui.settings.SettingsScreen
import ai.bayan.android.ui.voices.VoicesScreen
import kotlinx.serialization.Serializable

@Serializable data object Home : NavKey
@Serializable data object History : NavKey
@Serializable data object SettingsKey : NavKey
@Serializable data object Models : NavKey
@Serializable data object Voices : NavKey
@Serializable data class HistoryDetail(val id: Long) : NavKey

private data class TopLevel(val key: NavKey, val label: Int, val icon: ImageVector, val selectedIcon: ImageVector)

private val TOP_LEVEL = listOf(
    TopLevel(Home, R.string.nav_simplify, Icons.Outlined.AutoAwesome, Icons.Rounded.AutoAwesome),
    TopLevel(History, R.string.nav_history, Icons.Outlined.History, Icons.Rounded.History),
    TopLevel(SettingsKey, R.string.nav_settings, Icons.Outlined.Settings, Icons.Rounded.Settings),
)

/** Opens [key] as the root of its own tab; tapping the current tab again returns to its root. */
private fun NavBackStack<NavKey>.selectTab(key: NavKey) {
    if (size == 1 && first() == key) return
    add(key)
    while (size > 1) removeAt(0)
}

@Composable
fun BayanNavigation(sharedText: String?, onSharedTextConsumed: () -> Unit) {
    val backStack = rememberNavBackStack(Home)
    val root = backStack.first()
    val top = backStack.last()
    val showBar = TOP_LEVEL.any { it.key == top }

    // Shared text always lands on the home screen.
    if (sharedText != null && root != Home) backStack.selectTab(Home)
    // Back from another tab's root goes to the home tab before leaving the app.
    BackHandler(enabled = backStack.size == 1 && root != Home) { backStack.selectTab(Home) }

    val type = if (showBar) NavigationSuiteScaffoldDefaults.navigationSuiteType(currentWindowAdaptiveInfo()) else NavigationSuiteType.None
    NavigationSuiteScaffold(
        navigationSuiteType = type,
        navigationItems = {
            TOP_LEVEL.forEach { dest ->
                val selected = root == dest.key
                NavigationSuiteItem(
                    selected = selected,
                    onClick = { backStack.selectTab(dest.key) },
                    icon = { Icon(if (selected) dest.selectedIcon else dest.icon, null) },
                    label = { Text(stringResource(dest.label)) },
                    navigationSuiteType = type,
                )
            }
        },
    ) {
        NavDisplay(
            backStack = backStack,
            onBack = { if (backStack.size > 1) backStack.removeAt(backStack.lastIndex) },
            entryDecorators = listOf(
                rememberSaveableStateHolderNavEntryDecorator(),
                rememberViewModelStoreNavEntryDecorator(),
            ),
            entryProvider = entryProvider {
                entry<Home> {
                    HomeScreen(
                        onOpenModels = { backStack.add(Models) },
                        sharedText = sharedText,
                        onSharedTextConsumed = onSharedTextConsumed,
                    )
                }
                entry<History> { HistoryScreen(onOpen = { backStack.add(HistoryDetail(it)) }) }
                entry<HistoryDetail> { key -> HistoryDetailScreen(key.id, onBack = { backStack.removeAt(backStack.lastIndex) }) }
                entry<SettingsKey> { SettingsScreen(onOpenModels = { backStack.add(Models) }, onOpenVoices = { backStack.add(Voices) }) }
                entry<Voices> { VoicesScreen(onBack = { backStack.removeAt(backStack.lastIndex) }) }
                entry<Models> { ModelsScreen(onBack = { backStack.removeAt(backStack.lastIndex) }) }
            },
        )
    }
}
