package ai.bayan.android.speech

import ai.bayan.android.BayanApp
import ai.bayan.android.R
import ai.bayan.android.ui.process.FloatingPanel
import ai.bayan.android.ui.process.FloatingReader
import ai.bayan.android.ui.process.ProcessTextActivity
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.drawable.Icon
import android.media.MediaMetadata
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.IBinder
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

/**
 * Keeps Bayan reading after the "تبسيط" panel is minimized, with the controls every media app has: the media
 * notification, the Quick Settings player and the lock screen. Tapping them reopens the panel where it was.
 */
class ReadingService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private lateinit var media: MediaSession
    /** The minimized panel floating over the current app, when Bayan may display over other apps. */
    private var floating: FloatingPanel? = null
    private val container get() = (application as BayanApp).container

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val nm = getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel(CHANNEL) == null) {
            val name = getString(R.string.notification_channel_reading)
            nm.createNotificationChannel(NotificationChannel(CHANNEL, name, NotificationManager.IMPORTANCE_LOW))
        }
        media = MediaSession(this, "Bayan").apply {
            setCallback(Controls())
            setSessionActivity(openPanel())
            isActive = true
        }
        if (android.provider.Settings.canDrawOverlays(this)) {
            floating = FloatingPanel(this).also { panel ->
                panel.show { move ->
                    FloatingReader(container, move, onExpand = ::openFullPanel, onClose = { container.overlay.close(); stopSelf() })
                }
            }
        }
        show(playing = true)
        // Mirror reading in the controls; once the panel is back on screen the controls go away.
        scope.launch {
            combine(container.readAloud.state, container.overlay.minimized) { speech, minimized -> speech to minimized }
                .collect { (speech, minimized) ->
                    if (!minimized) stopSelf() else show(playing = speech is SpeechState.Speaking)
                }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_TOGGLE -> if (container.overlay.isReading) container.overlay.pause() else container.overlay.play()
            ACTION_STOP -> { container.overlay.close(); stopSelf() }
        }
        return START_NOT_STICKY
    }

    private fun openFullPanel() {
        startActivity(Intent(this, ProcessTextActivity::class.java).setAction(ProcessTextActivity.ACTION_RESUME).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    override fun onDestroy() {
        floating?.remove()
        floating = null
        scope.cancel()
        media.release()
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    private inner class Controls : MediaSession.Callback() {
        override fun onPlay() = container.overlay.play()
        override fun onPause() = container.overlay.pause()
        override fun onStop() {
            container.overlay.close()
            stopSelf()
        }
    }

    /** Updates the media session and its notification; foreground only while reading, so a paused one can be swiped away. */
    private fun show(playing: Boolean) {
        val title = container.overlay.title()
        media.setMetadata(
            MediaMetadata.Builder()
                .putString(MediaMetadata.METADATA_KEY_TITLE, title)
                .putString(MediaMetadata.METADATA_KEY_ARTIST, getString(R.string.app_name))
                .build(),
        )
        val state = if (playing) PlaybackState.STATE_PLAYING else PlaybackState.STATE_PAUSED
        media.setPlaybackState(
            PlaybackState.Builder()
                .setActions(PlaybackState.ACTION_PLAY or PlaybackState.ACTION_PAUSE or PlaybackState.ACTION_PLAY_PAUSE or PlaybackState.ACTION_STOP)
                .setState(state, PlaybackState.PLAYBACK_POSITION_UNKNOWN, 1f)
                .build(),
        )
        val toggleIcon = if (playing) R.drawable.ic_media_pause else R.drawable.ic_media_play
        val toggleLabel = getString(if (playing) R.string.action_stop else R.string.action_listen)
        val notification = Notification.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_bayan)
            .setContentTitle(title)
            .setContentText(getString(R.string.app_name))
            .setContentIntent(openPanel())
            .setDeleteIntent(command(ACTION_STOP))
            .setVisibility(Notification.VISIBILITY_PUBLIC)
            .addAction(Notification.Action.Builder(Icon.createWithResource(this, toggleIcon), toggleLabel, command(ACTION_TOGGLE)).build())
            .setStyle(Notification.MediaStyle().setMediaSession(media.sessionToken).setShowActionsInCompactView(0))
            .setOngoing(playing || floating != null)
            .build()
        // Foreground while reading, and while the floating panel is on screen; otherwise the controls can be swiped away.
        if (playing || floating != null) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK)
        } else {
            stopForeground(STOP_FOREGROUND_DETACH)
            getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification)
        }
    }

    private fun command(action: String): PendingIntent =
        PendingIntent.getService(this, action.hashCode(), Intent(this, ReadingService::class.java).setAction(action), PendingIntent.FLAG_IMMUTABLE)

    private fun openPanel(): PendingIntent =
        PendingIntent.getActivity(
            this, 0,
            Intent(this, ProcessTextActivity::class.java).setAction(ProcessTextActivity.ACTION_RESUME).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

    companion object {
        private const val CHANNEL = "reading"
        private const val NOTIFICATION_ID = 7
        private const val ACTION_TOGGLE = "ai.bayan.android.READING_TOGGLE"
        private const val ACTION_STOP = "ai.bayan.android.READING_STOP"
    }
}
