(function () {
  const PLATFORM_ICONS = {
    youtube: '▶️',
    tiktok: '🎵',
    instagram: '📷',
    facebook: '📘',
    threads: '🧵',
    x: '✖️',
    linkedin: '💼',
    bluesky: '🦋',
    pinterest: '📌',
  };

  window.AutoVideoUI = {
    platformIcon(platform) {
      return PLATFORM_ICONS[platform] || '🔗';
    },
    emptyPlatformMeta(platforms = []) {
      return Object.fromEntries(
        platforms.map((platform) => [
          platform,
          {
            title: '',
            description: '',
            tags: '',
            first_comment: '',
            video_version: 'legacy',
            use_auto_thumbnail: false,
          },
        ])
      );
    },
  };
})();
