package ai.bayan.android.ui.history

import android.content.Context
import android.text.format.DateUtils
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.DeleteSweep
import androidx.compose.material.icons.rounded.History
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LargeFlexibleTopAppBar
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedListItem
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.material3.rememberTopAppBarState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import ai.bayan.android.AppContainer
import ai.bayan.android.R
import ai.bayan.android.data.HistoryItem
import ai.bayan.android.ui.appViewModel
import ai.bayan.android.ui.components.SectionHeader
import ai.bayan.android.ui.theme.ContentDirection
import kotlinx.coroutines.launch

class HistoryViewModel(private val app: AppContainer) : ViewModel() {
    val items = app.history.items
    fun remove(item: HistoryItem) = viewModelScope.launch { app.history.remove(item.id) }
    fun restore(item: HistoryItem) = viewModelScope.launch { app.history.restore(item) }
    fun clear() = viewModelScope.launch { app.history.clear() }
}

/** "Today", "Yesterday" or the date, as the system's own apps group lists. */
private fun dayLabel(context: Context, time: Long): String = when {
    DateUtils.isToday(time) -> context.getString(R.string.history_today)
    DateUtils.isToday(time + DateUtils.DAY_IN_MILLIS) -> context.getString(R.string.history_yesterday)
    else -> DateUtils.formatDateTime(context, time, DateUtils.FORMAT_SHOW_DATE or DateUtils.FORMAT_SHOW_WEEKDAY)
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun HistoryScreen(onOpen: (Long) -> Unit, vm: HistoryViewModel = appViewModel { HistoryViewModel(it) }) {
    val items by vm.items.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val appBar = TopAppBarDefaults.exitUntilCollapsedScrollBehavior(rememberTopAppBarState())
    var confirmClear by rememberSaveable { mutableStateOf(false) }
    val deleted = stringResource(R.string.history_deleted)
    val undo = stringResource(R.string.action_undo)
    val groups = remember(items) { items.groupBy { dayLabel(context, it.createdAt) } }

    Scaffold(
        modifier = Modifier.nestedScroll(appBar.nestedScrollConnection),
        topBar = {
            LargeFlexibleTopAppBar(
                title = { Text(stringResource(R.string.nav_history)) },
                actions = {
                    if (items.isNotEmpty()) {
                        IconButton(onClick = { confirmClear = true }) { Icon(Icons.Rounded.DeleteSweep, stringResource(R.string.history_clear)) }
                    }
                },
                scrollBehavior = appBar,
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        if (items.isEmpty()) {
            EmptyHistory(Modifier.padding(padding))
            return@Scaffold
        }
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            LazyColumn(
                Modifier.widthIn(max = 720.dp).fillMaxWidth(),
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 24.dp),
                verticalArrangement = Arrangement.spacedBy(ListItemDefaults.SegmentedGap),
            ) {
                groups.forEach { (day, dayItems) ->
                    item(key = "header:$day") { SectionHeader(day, Modifier.animateItem()) }
                    itemsIndexed(dayItems, key = { _, it -> it.id }) { index, item ->
                        HistoryRow(
                            item = item,
                            index = index,
                            count = dayItems.size,
                            onClick = { onOpen(item.id) },
                            onDelete = {
                                vm.remove(item)
                                scope.launch {
                                    val result = snackbar.showSnackbar(deleted, undo, withDismissAction = true)
                                    if (result == SnackbarResult.ActionPerformed) vm.restore(item)
                                }
                            },
                            modifier = Modifier.animateItem(),
                        )
                    }
                }
            }
        }
    }

    if (confirmClear) {
        AlertDialog(
            onDismissRequest = { confirmClear = false },
            icon = { Icon(Icons.Rounded.DeleteSweep, null) },
            title = { Text(stringResource(R.string.history_clear_title)) },
            text = { Text(stringResource(R.string.history_clear_body)) },
            confirmButton = { TextButton(onClick = { vm.clear(); confirmClear = false }) { Text(stringResource(R.string.action_clear_all)) } },
            dismissButton = { TextButton(onClick = { confirmClear = false }) { Text(stringResource(R.string.action_cancel)) } },
        )
    }
}

@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
private fun HistoryRow(item: HistoryItem, index: Int, count: Int, onClick: () -> Unit, onDelete: () -> Unit, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val haptics = LocalHapticFeedback.current
    val dismiss = rememberSwipeToDismissBoxState()
    SwipeToDismissBox(
        state = dismiss,
        modifier = modifier,
        backgroundContent = {
            Box(Modifier.fillMaxSize().padding(horizontal = 24.dp), contentAlignment = Alignment.CenterEnd) {
                Icon(Icons.Rounded.DeleteOutline, stringResource(R.string.action_delete), tint = MaterialTheme.colorScheme.error)
            }
        },
        enableDismissFromStartToEnd = false,
        onDismiss = { haptics.performHapticFeedback(HapticFeedbackType.GestureThresholdActivate); onDelete() },
    ) {
        SegmentedListItem(
            onClick = onClick,
            shapes = ListItemDefaults.segmentedShapes(index, count),
            supportingContent = { Text(item.source, maxLines = 1, overflow = TextOverflow.Ellipsis, style = LocalTextStyle.current.merge(ContentDirection)) },
            trailingContent = {
                Text(
                    DateUtils.formatDateTime(context, item.createdAt, DateUtils.FORMAT_SHOW_TIME),
                    style = MaterialTheme.typography.labelMedium,
                )
            },
        ) {
            Text(item.result, maxLines = 2, overflow = TextOverflow.Ellipsis, style = LocalTextStyle.current.merge(ContentDirection))
        }
    }
}

@Composable
private fun EmptyHistory(modifier: Modifier = Modifier) {
    Column(
        modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(Icons.Rounded.History, null, Modifier.size(56.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            stringResource(R.string.history_empty_title),
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(top = 16.dp, bottom = 8.dp),
        )
        Text(
            stringResource(R.string.history_empty_body),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}
