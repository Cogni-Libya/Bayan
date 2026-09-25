package ai.bayan.android.ui

/**
 * Sealed hierarchy governing the reactive UI states of [SimplifiedBottomSheetDialogFragment].
 *
 * Implements Requirements R3 and R4:
 * - [NeedsModel]: Model weights not ready; displays guidance and download CTA.
 * - [Loading]: Indeterminate progress indicator while simplification engine runs.
 * - [Result]: Displays simplified and original text with dyslexia typography and toggle control.
 * - [Error]: Displays localized error message while preserving the readable original Arabic text.
 */
sealed class SheetState {
    data class NeedsModel(val message: String? = null) : SheetState()
    object Loading : SheetState()
    data class Result(
        val originalText: String,
        val simplifiedText: String,
        val isShowingSimplifiedLarge: Boolean = true
    ) : SheetState()
    data class Error(
        val originalText: String,
        val errorMessage: String
    ) : SheetState()
}
