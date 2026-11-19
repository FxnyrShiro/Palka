# palka

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Made with PyQt6](https://img.shields.io/badge/Made%20with-PyQt6-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
![Platform](https://img.shields.io/badge/platform-linux-lightgrey)
![Status](https://img.shields.io/badge/status-active-brightgreen)

> Минималистичный браузер на PyQt6/QtWebEngine с кастомной поддержкой **WebUSB**,
> достаточной для прошивки Nintendo Switch через [WebRCM][webrcm].

Проект создан как альтернатива для сред, где нет удобного доступа к Chromium: 
Firefox не поддерживает WebUSB, а сборка бинарного Chrome в некоторых 
дистрибутивах (например, Gentoo) нецелесообразна. Решает специфическую 
задачу — запуск WebRCM без нативного браузера.

[webrcm]: https://reubenjds.github.io/webrcm/

---

## Ключевые особенности

- **WebUSB через `navigator.usb`** — реализован как кастомный шим поверх 
  системных вызовов `USBDEVFS_SUBMITURB` + `DISCARDURB`. Позволяет обходить 
  лимит libusb в 4096 байт для триггера эксплойта Fusée Gelée. 
  *Примечание: реализация заточена под WebRCM и не является универсальным WebUSB.*
- **Менеджер паролей** с автозаполнением. Поддерживает сложные SPA-логины 
  (Google, Reddit и др.), где поля email и пароля находятся на разных экранах, 
  за счет перехвата `history.pushState` и `MutationObserver`.
- **Закладки, история, загрузки** — с кастомной панелью прогресса.
- **Кастомный UI** — мятно-лавандовая палитра, стилизованный tab bar.
- **Управление окном** — `F11` для полноэкранного режима (с корректной обработкой 
  fullscreen-запросов от YouTube/Twitch).
- **DevTools, поиск, зум, экспорт в PDF, `view-source:`**

## Технические ограничения

- **Архитектура Linux:** используется прямой `ioctl` к `/dev/bus/usb/`, поэтому 
  проект работает только на Linux.
- **Расширения Chromium:** не поддерживаются из-за ограничений QtWebEngine.
- **WebUSB:** реализован только для профиля WebRCM. Теоретически обобщается 
  на другие устройства, но требует доработки `_on_control_transfer_in`.

---

## Требования и установка

- Linux (X11 или Wayland)
- Python 3.11+
- `PyQt6`, `PyQt6-WebEngine`, `pyusb`, `QtWebEngine`

### 1. Зависимости (пример для Gentoo)
```bash
emerge --ask dev-python/pyqt6 dev-python/pyqt6-webengine dev-python/pyusb dev-qt/qtwebengine
```

### 2. Настройка окружения
Для работы WebUSB необходимо увеличить лимит usbfs (сбрасывается при перезагрузке):
```bash
echo 1000 | sudo tee /sys/module/usbcore/parameters/usbfs_memory_mb
```
*(Для постоянного применения добавьте параметр в `/etc/sysctl.d/`)*

Добавьте udev-правило для Nintendo Switch в RCM:
```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0955", ATTR{idProduct}=="7321", MODE="0666", TAG+="uaccess"' \
  | sudo tee /etc/udev/rules.d/50-nintendo-switch.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### 3. Запуск
```bash
./browser.sh
```

---

## Детали реализации WebUSB-триггера

Эксплойт Fusée Gelée (Tegra X1) требует отправки control-трансфера с `wLength=0x7000` (28672 байт). Стандартный `pyusb.ctrl_transfer` не способен на это, так как libusb ограничивает размер буфера константой `MAX_CTRL_BUFFER_LENGTH = 4096`.

Для обхода ограничения используется прямая работа с URB (USB Request Block) через `ioctl` к ноду `/dev/bus/usb/`:

1. **`USBDEVFS_SUBMITURB`** — setup-пакет ставится в очередь контроллера.
2. **Задержка 1 мс** — setup успевает уйти на устройство, но URB еще не завершается (при 5 мс discard вернет `EINVAL`, при 0 мс setup не успеет уйти).
3. **`USBDEVFS_DISCARDURB`** — отмена URB до завершения, что и вызывает переполнение стека в bootROM Tegra.

*Данный подход был воспроизведен на основе анализа поведения Google Chrome через `strace` (Chrome делает то же самое, но через libusb в двух процессах).*

---

## Известные ограничения и Research

### Ограничение FPS в QtWebEngine (60 Hz)
На мониторах 120/144/180 Hz QtWebEngine упирается в 60 FPS, в отличие от нативного Chrome. 

**Результаты исследования:**
- `QScreen.refreshRate()` возвращает корректные 179.99 Hz.
- Чистый QML без WebEngine рендерит 200 FPS.
- Отключение VSYNC (`QSG_NO_VSYNC=1`), `vblank_mode=0` и флаги Chromium (`--disable-gpu-vsync`) не снимают ограничение.

**Причина:** Chromium-композитор внутри QtWebEngine не получает корректный vsync-сигнал выше 60 Hz. Каждый кадр проходит через `RenderWidgetHostViewQtDelegate` и дефолтится к 60 Hz `viz::BeginFrameSource`, в то время как нативный Chrome использует прямой Ozone/Wayland-путь с dmabuf. 
*Решение:* Требуется патч исходников QtWebEngine (5–10 строк в `render_widget_host_view_qt_delegate_quick.cpp`) и пересборка.

### Тёмная тема сайтов
Текущая сборка QtWebEngine не поддерживает `QWebEngineProfile.setColorScheme()`. Форсирование `prefers-color-scheme` через JS-инъекцию ломает работу hCaptcha (антибот детектит override `window.matchMedia`). *Решение:* переключение темной темы на уровне самих сайтов.

---

## Архитектура проекта

```text
palka/
├── __init__.py         # переменные окружения Chromium
├── __main__.py         # точка входа
├── constants.py        # цвета, пути, константы
├── theme.py            # тёмная палитра Qt
├── storage.py          # JSON-хранилище + обфускация паролей
├── styles.py           # QSS для диалогов
├── widgets.py          # StyledTabBar
├── passwords.py        # менеджер паролей
├── bookmarks.py        # закладки
├── history.py          # история
├── downloads.py        # загрузки
├── managers_ui.py      # диалог менеджера
├── permissions.py      # диалог разрешений
├── usb_bridge.py       # Ядро WebUSB-шима (SUBMITURB + DISCARDURB)
├── browser_page.py     # QWebEnginePage с инжектами
├── browser_window.py   # главное окно
└── js/
    ├── passwords.js    # автозаполнение (SPA-логины)
    └── webusb_shim.js  # шим navigator.usb
```

---

## Roadmap (Планы по развитию)

- [ ] Покрытие ключевых модулей (`storage`, `usb_bridge`) unit-тестами.
- [ ] Рефакторинг `usb_bridge.py` для поддержки произвольных WebUSB-устройств.
- [ ] Изучение возможности применения патча для снятия лимита 60 FPS в QtWebEngine.

---

## Лицензия

[GPL-3.0](LICENSE).

## Благодарности

- [WebRCM][webrcm] — за логику прошивки
- [fusee-launcher](https://github.com/ktemkin/fusee-launcher) — за понимание протокола Tegra RCM
- [Qt](https://www.qt.io/) и [Chromium](https://www.chromium.org/) — за движок
