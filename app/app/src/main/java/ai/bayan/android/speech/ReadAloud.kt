package ai.bayan.android.speech

import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import ai.bayan.android.data.SettingsRepository
import ai.bayan.android.model.ModelState
import ai.bayan.android.model.ModelStore
import java.util.Locale
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

sealed interface SpeechState {
    data object Unavailable : SpeechState
    data object MissingArabicVoice : SpeechState
    data object Idle : SpeechState
    /** [start] until [end] is the word being spoken in the text with [key]; empty while the next sentence is prepared. */
    data class Speaking(val key: String, val start: Int, val end: Int) : SpeechState
}

/**
 * Reads Arabic text aloud and reports the word being spoken. It streams: text can be handed over while it is still
 * being simplified ([follow]), and each sentence plays as soon as it is ready, while the next one is prepared.
 * The voice is the user's choice: an on-device sherpa-onnx voice, or the phone's own text-to-speech engine.
 */
class ReadAloud(context: Context, private val scope: CoroutineScope, settings: SettingsRepository, store: ModelStore) {
    private val app = context.applicationContext
    private val audio = app.getSystemService(AudioManager::class.java)

    /** The voice in use: the chosen one if it is installed, otherwise the system voice. */
    val voice: StateFlow<VoiceInfo> = combine(settings.settings, store.states) { s, states ->
        VoiceCatalog.get(s.voice).takeIf { it.engine == VoiceEngine.System || states[it.id] is ModelState.Installed } ?: VoiceCatalog.system
    }.stateIn(scope, SharingStarted.Eagerly, VoiceCatalog.system)

    private val systemStatus = MutableStateFlow<SpeechState>(SpeechState.Unavailable)
    private val speaking = MutableStateFlow<SpeechState.Speaking?>(null)
    val state: StateFlow<SpeechState> = combine(voice, systemStatus, speaking) { v, system, now ->
        now ?: if (v.engine == VoiceEngine.System) system else SpeechState.Idle
    }.stateIn(scope, SharingStarted.Eagerly, SpeechState.Idle)

    private val store = store
    private var tts: TextToSpeech? = null
    private val arabic = Locale.forLanguageTag("ar")

    /** The text being read: sentences are queued as they arrive. */
    private class Stream(val key: String, val rate: Float, val voice: VoiceInfo, val generation: Int) {
        var queuedUpTo = 0
        var ended = false
        @Volatile var pending = 0
        val segments = Channel<Segment>(Channel.UNLIMITED)
        var job: Job? = null
    }
    private data class Segment(val text: String, val start: Int)
    @Volatile private var stream: Stream? = null
    private var generation = 0

    init {
        tts = TextToSpeech(app) { status ->
            val engine = tts
            if (status != TextToSpeech.SUCCESS || engine == null) { systemStatus.value = SpeechState.Unavailable; return@TextToSpeech }
            val lang = engine.setLanguage(arabic)
            systemStatus.value = if (lang == TextToSpeech.LANG_MISSING_DATA || lang == TextToSpeech.LANG_NOT_SUPPORTED) {
                SpeechState.MissingArabicVoice
            } else SpeechState.Idle
            engine.setOnUtteranceProgressListener(SystemListener())
        }
    }

    /** Reads [text] from the start. */
    fun speak(key: String, text: String, rate: Float) {
        stop()
        follow(key, text, finished = true, rate = rate)
    }

    /**
     * Reads a text that is still growing: call it again whenever more finished sentences are available, with
     * [finished] once the text is complete. Already queued text is not read twice.
     */
    fun follow(key: String, text: String, finished: Boolean, rate: Float, voiceOverride: VoiceInfo? = null, startAt: Int = 0) {
        var s = stream
        if (s == null || s.key != key) {
            stop()
            s = Stream(key, rate, voiceOverride ?: voice.value, ++generation).also { stream = it }
            // Resuming: start at the beginning of the sentence that holds [startAt].
            if (startAt > 0) s.queuedUpTo = sentences(text, 0).lastOrNull { it.first <= startAt }?.first ?: 0
            speaking.value = SpeechState.Speaking(key, 0, 0)
            if (s.voice.engine == VoiceEngine.System) {
                if (systemStatus.value != SpeechState.Idle) { stop(); return }
                tts?.setSpeechRate(rate)
            } else {
                s.job = scope.launch(Dispatchers.IO) { playOnDevice(s) }
            }
        }
        if (text.length > s.queuedUpTo) {
            for (range in sentences(text, s.queuedUpTo)) enqueue(s, Segment(text.substring(range), range.first))
            s.queuedUpTo = text.length
        }
        if (finished && !s.ended) {
            s.ended = true
            s.segments.close()
            if (s.voice.engine == VoiceEngine.System && s.pending == 0) finish(s)
        }
    }

    /** Plays a short sample with [voice], whether or not it is the chosen one. */
    fun preview(voice: VoiceInfo, text: String, rate: Float) {
        stop()
        follow("preview:${voice.id}", text, finished = true, rate = rate, voiceOverride = voice)
    }

    fun stop() {
        val s = stream ?: return
        stream = null
        generation++
        s.job?.cancel()
        s.segments.cancel()
        if (s.voice.engine == VoiceEngine.System) tts?.stop()
        speaking.value = null
        abandonFocus()
    }

    fun isSpeaking(key: String): Boolean = stream?.key == key

    fun installVoiceIntent(): Intent =
        Intent(TextToSpeech.Engine.ACTION_INSTALL_TTS_DATA).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    private fun enqueue(s: Stream, segment: Segment) {
        if (s.voice.engine == VoiceEngine.System) {
            s.pending++
            if (s.pending == 1) requestFocus()
            tts?.speak(segment.text, TextToSpeech.QUEUE_ADD, Bundle(), "${s.generation}|${segment.start}")
        } else {
            s.segments.trySend(segment)
        }
    }

    private fun finish(s: Stream) {
        if (stream !== s) return
        stream = null
        speaking.value = null
        abandonFocus()
    }

    private inner class SystemListener : UtteranceProgressListener() {
        private fun parse(id: String): Pair<Stream, Int>? {
            val (gen, start) = id.split('|').takeIf { it.size == 2 } ?: return null
            val s = stream?.takeIf { it.generation == gen.toIntOrNull() } ?: return null
            return s to (start.toIntOrNull() ?: 0)
        }
        override fun onStart(id: String) {}
        override fun onRangeStart(id: String, start: Int, end: Int, frame: Int) {
            val (s, base) = parse(id) ?: return
            speaking.value = SpeechState.Speaking(s.key, base + start, base + end)
        }
        override fun onDone(id: String) {
            val (s, _) = parse(id) ?: return
            s.pending--
            if (s.pending <= 0 && s.ended) finish(s)
        }
        override fun onStop(id: String, interrupted: Boolean) {}
        @Deprecated("Deprecated in Java")
        override fun onError(id: String) = onDone(id)
    }

    // --- On-device voices -------------------------------------------------------------------------------------

    private val voiceLock = Mutex()
    private var loaded: SherpaVoice? = null

    @OptIn(ExperimentalCoroutinesApi::class)
    private val synthesis = Dispatchers.Default.limitedParallelism(1)

    private suspend fun load(voice: VoiceInfo): SherpaVoice = voiceLock.withLock {
        loaded?.takeIf { it.voice.id == voice.id }?.let { return it }
        withContext(synthesis) {
            loaded?.close()
            loaded = null
            val dir = store.installedDir(voice.id) ?: error("Voice ${voice.id} is not installed")
            val t = System.nanoTime()
            SherpaVoice(voice, dir, SherpaVoice.espeakData(app)).also {
                loaded = it
                android.util.Log.i("Bayan", "voice ${voice.id} loaded in ${(System.nanoTime() - t) / 1_000_000} ms")
            }
        }
    }

    /** Loads the chosen on-device voice ahead of time, so reading can start the moment the first sentence is ready. */
    fun warmUp() {
        val v = voice.value
        if (v.engine != VoiceEngine.System) scope.launch(Dispatchers.IO) { runCatching { load(v) } }
    }

    /** Frees the on-device voice when nothing is being read. */
    fun releaseIfIdle() {
        if (stream != null || !voiceLock.tryLock()) return
        try { loaded?.close(); loaded = null } finally { voiceLock.unlock() }
    }

    /** One sentence's place in the audio stream, with each word's share of it for highlighting. */
    private class Span(val startFrame: Long, val frames: Int, val base: Int, val words: List<IntRange>, val weights: FloatArray)

    private suspend fun playOnDevice(s: Stream) = coroutineScope {
        val voice = runCatching { load(s.voice) }.getOrElse { finish(s); return@coroutineScope }
        val rate = voice.sampleRate
        val audioChannel = Channel<Pair<Segment, FloatArray>>(capacity = 1)
        // Synthesis runs one sentence ahead of playback.
        launch(synthesis) {
            try {
                for (segment in s.segments) {
                    val t = System.nanoTime()
                    val pcm = voice.generate(segment.text, s.rate)
                    android.util.Log.i("Bayan", "tts ${pcm.size * 1000L / rate} ms of audio in ${(System.nanoTime() - t) / 1_000_000} ms")
                    audioChannel.send(segment to pcm)
                }
            } finally {
                audioChannel.close()
            }
        }

        val track = AudioTrack.Builder()
            .setAudioAttributes(ATTRIBUTES)
            .setAudioFormat(
                AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_FLOAT).setSampleRate(rate)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build(),
            )
            .setTransferMode(AudioTrack.MODE_STREAM)
            .setBufferSizeInBytes(maxOf(AudioTrack.getMinBufferSize(rate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_FLOAT), rate))
            .build()
        val timeline = ArrayList<Span>()
        var written = 0L
        requestFocus()
        track.play()
        val ticker = launch {
            var last: SpeechState.Speaking? = null
            while (isActive) {
                val position = track.playbackHeadPosition.toLong() and 0xffffffffL
                val span = synchronized(timeline) { timeline.lastOrNull { position >= it.startFrame } }
                if (span != null) {
                    val word = wordAt(span, ((position - span.startFrame).toFloat() / span.frames).coerceIn(0f, 1f))
                    val now = SpeechState.Speaking(s.key, span.base + word.first, span.base + word.last + 1)
                    if (now != last && stream === s) { speaking.value = now; last = now }
                }
                delay(40)
            }
        }
        try {
            for ((segment, pcm) in audioChannel) {
                val words = WORD.findAll(segment.text).map { it.range }.toList()
                val weights = FloatArray(words.size) { i ->
                    val w = segment.text.substring(words[i])
                    w.count { it.isLetter() } + if (w.last() in PAUSES) 4f else 1f
                }
                synchronized(timeline) { timeline += Span(written, pcm.size, segment.start, words, weights) }
                var offset = 0
                while (offset < pcm.size && stream === s) {
                    val n = track.write(pcm, offset, minOf(4096, pcm.size - offset), AudioTrack.WRITE_BLOCKING)
                    if (n <= 0) break
                    offset += n
                }
                written += pcm.size
            }
            withContext(Dispatchers.Default) {
                while (stream === s && (track.playbackHeadPosition.toLong() and 0xffffffffL) < written) delay(40)
            }
        } finally {
            ticker.cancel()
            runCatching { track.pause(); track.flush(); track.release() }
            finish(s)
        }
    }

    private fun wordAt(span: Span, fraction: Float): IntRange {
        if (span.words.isEmpty()) return IntRange.EMPTY
        val total = span.weights.sum()
        var acc = 0f
        for (i in span.words.indices) {
            acc += span.weights[i]
            if (fraction * total <= acc) return span.words[i]
        }
        return span.words.last()
    }

    // --- Audio focus: other apps lower their volume while Bayan reads. ------------------------------------------

    private val focus = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
        .setAudioAttributes(ATTRIBUTES)
        .setOnAudioFocusChangeListener { change -> if (change == AudioManager.AUDIOFOCUS_LOSS) scope.launch(Dispatchers.Main) { stop() } }
        .build()

    private fun requestFocus() { audio.requestAudioFocus(focus) }
    private fun abandonFocus() { audio.abandonAudioFocusRequest(focus) }

    fun shutdown() {
        stop()
        tts?.shutdown()
        tts = null
        loaded?.close()
    }

    companion object {
        private val ATTRIBUTES = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_MEDIA)
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
            .build()
        private val WORD = Regex("\\S+")
        private const val PAUSES = ".,!?؟،؛:"
        private val SENTENCE = Regex("[^.!?؟\\n]+[.!?؟]*")

        /** Sentence ranges of [text] from [from] on, trimmed of spaces. */
        fun sentences(text: String, from: Int): List<IntRange> =
            SENTENCE.findAll(text, from).mapNotNull { m ->
                val r = m.range
                var a = r.first
                var b = r.last
                while (a <= b && text[a].isWhitespace()) a++
                while (b >= a && text[b].isWhitespace()) b--
                if (a <= b) a..b else null
            }.toList()
    }
}
