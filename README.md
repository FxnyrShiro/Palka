# palka

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Made with PyQt6](https://img.shields.io/badge/Made%20with-PyQt6-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
![vibe-coded](https://img.shields.io/badge/code-vibe--coded-b388ff?style=flat-square)
![status](https://img.shields.io/badge/status-works%20on%20my%20machine-00ffaa?style=flat-square)

> Минималистичный браузер на PyQt6/QtWebEngine с поддержкой **WebUSB**,
> достаточной для прошивки Nintendo Switch через [WebRCM][webrcm].

Задумывался как ответ на простую проблему: Firefox не поддерживает WebUSB,
Chromium в Gentoo объявили deprecated, а ставить бинарный Chrome не хочется.
Вот и появился этот велосипед.

[webrcm]: https://reubenjds.github.io/webrcm/

---

> ⚠️ **Дисклеймер:** этот код написан в режиме «вайб-кодинга» — с
> помощью LLM, методом проб и ошибок, без тестов и code review.
> Работает — но не удивляйтесь странным решениям. Подробности
> в разделе [«О качестве кода»](#о-качестве-кода).

---

## Возможности

- **WebUSB через `navigator.usb`** — реализован как шим поверх
  `USBDEVFS_SUBMITURB` + `DISCARDURB` (обход лимита libusb в 4096 байт).
  **Внимание:** это не полноценный WebUSB, а хак, заточенный под
  конкретный сценарий WebRCM. Работает — но не ждите, что заведётся
  любое другое WebUSB-устройство.
- **Менеджер паролей** с автозаполнением, включая SPA-логины (Google,
  Reddit и прочие, где email и пароль на разных экранах)
- **Закладки, история, загрузки** — с выпадающей панелью прогресса
- **Кастомный UI** — мятно-лавандовая палитра, стилизованный tab bar
- **Fullscreen** — `F11` для окна, отдельная обработка fullscreen
  от страницы (YouTube, Twitch — панели скрываются)
- **DevTools, поиск, зум, печать в PDF, `view-source:`**

## Чего не умеет

- **Расширений Chromium** — QtWebEngine их не поддерживает
- **Синхронизации и аккаунтов** — по понятным причинам
- **Тёмной темы для сайтов «из коробки»** — см. «Известные ограничения»
- **Работать не на Linux** — используется `ioctl` к `/dev/bus/usb/`

---

## Требования

- Linux
- Python 3.11+
- `PyQt6`, `PyQt6-WebEngine`, `pyusb`, `QtWebEngine`

## Установка

### 1. Зависимости

```bash
# Gentoo
emerge --ask dev-python/pyqt6 dev-python/pyqt6-webengine dev-python/pyusb dev-qt/qtwebengine
```

### 2. Настройка для WebUSB

Увеличить лимит usbfs (сбрасывается при перезагрузке):

```bash
echo 1000 | sudo tee /sys/module/usbcore/parameters/usbfs_memory_mb
```

Для постоянного применения добавь в `/etc/sysctl.d/` или в init-скрипт —
зависит от системы.

udev-правило для Nintendo Switch в RCM:

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

## Горячие клавиши

| Клавиши | Действие |
|---------|----------|
| `Ctrl+T` | Новая вкладка |
| `Ctrl+W` | Закрыть вкладку |
| `Ctrl+Shift+T` | Вернуть закрытую |
| `Ctrl+L` | Фокус в адресную строку |
| `Ctrl+F` | Поиск по странице |
| `Ctrl+H` | Менеджер (закладки, история, пароли) |
| `Ctrl+J` | Загрузки |
| `Ctrl+D` | Добавить в закладки |
| `F11` | Полный экран |
| `F12` / `Ctrl+Shift+I` | DevTools |
| `Ctrl+=` / `Ctrl+-` / `Ctrl+0` | Зум |
| `Ctrl+P` | Печать в PDF |
| `Ctrl+U` | Просмотр кода страницы |

---

## Как работает WebUSB-триггер

Fusée Gelée (эксплойт Tegra X1) требует отправки control-трансфера
`wLength=0x7000` (28672 байт). Стандартный `pyusb.ctrl_transfer`
не может этого сделать — libusb режет по
`MAX_CTRL_BUFFER_LENGTH = 4096`.

Решение — обход libusb и прямой `ioctl` к ноду `/dev/bus/usb/`:

1. **`USBDEVFS_SUBMITURB`** — setup-пакет уходит в очередь контроллера
2. **Пауза 1 мс** — setup успевает уйти на устройство, но URB ещё не
   завершается
   - с 5 мс URB успевает завершиться, discard получает `EINVAL`
   - с 0 мс setup не успевает уйти на устройство
3. **`USBDEVFS_DISCARDURB`** — отмена URB до завершения, что и триггерит
   переполнение стека в bootROM Tegra

Плюс нужен `usbfs_memory_mb >= 32` в параметрах ядра.

Этот подход подсмотрен в `strace` от Google Chrome, который делает то же
самое через libusb, но с двух процессов (submit в одном, discard в другом).

**Никаких ZLP** между чанками bulk-трансфера — Chrome их тоже не шлёт.
Сначала мы отправляли 45 лишних пустых пакетов, и Tegra их не понимала.

---

## Известные ограничения

### Тёмная тема сайтов

QtWebEngine в текущей сборке не поддерживает
`QWebEngineProfile.setColorScheme()`. Мы пытались форсить
`prefers-color-scheme` через JS-инъекцию, но это ломало hCaptcha —
антибот детектит override `window.matchMedia`.

**Решение:** переключай тёмную тему в настройках каждого сайта вручную.
Google, YouTube, GitHub — у всех есть свой тумблер.

### FPS ограничен 60

На системах с мониторами 120/144/180 Hz QtWebEngine упирается в 60 FPS,
хотя нативный Chrome на той же системе выдаёт 130+. Для видео разницы
нет (источник всё равно 60), но скролл и CSS-анимации идут на 60
вместо реальной частоты монитора.

**Что было проверено:**

- `QScreen.refreshRate()` возвращает правильные 179.99 Hz — Qt видит
  реальную частоту.
- Чистый QML без WebEngine рендерит 200 FPS — Qt Quick сам по себе
  не ограничен.
- QtWebEngine в QML — 60 FPS. QtWebEngine в QWidget — 60 FPS.
- `QSG_NO_VSYNC=1`, `QSG_RENDER_LOOP=basic`,
  `QSG_USE_SIMPLE_ANIMATION_DRIVER=1`, `vblank_mode=0`,
  `QSurfaceFormat.setSwapInterval(0)` — не помогают.
- `--disable-gpu-vsync` + `--disable-frame-rate-limit` — снимают
  рывки, но ломают воспроизведение YouTube. Кэп при этом остаётся.
- Wayland и Xwayland — одинаковый результат.

**Причина:** Chromium-композитор внутри QtWebEngine не получает от
Qt Quick корректный vsync-сигнал на частоте выше 60 Hz. Каждый кадр
проходит через `RenderWidgetHostViewQtDelegate` и дефолтится к
60 Hz `viz::BeginFrameSource`, независимо от того, что монитор
работает на 144/180 Hz. В нативном Chrome используется прямой
Ozone/Wayland-путь с dmabuf, минуя Qt — отсюда разница.

**Решение:** ждать апстрим-фикс в QtWebEngine. Патч возможен (5–10
строк в `render_widget_host_view_qt_delegate_quick.cpp`), но требует
дня-двух чтения исходников и пересборки QtWebEngine, что окупается
только если ты хочешь именно это.

**Что можно сделать сейчас:** ничего. 60 FPS стабильны и без рывков —
для чтения, почты, работы этого достаточно. Единственный сценарий,
где разница реально заметна — если поставить рядом окно нативного
Chrome и скроллить синхронно.

### WebUSB только для WebRCM

Теоретически можно обобщить на другие устройства, но требует доработки
`_on_control_transfer_in` под конкретные сценарии.

---

## Структура

```
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
├── downloads.py        # загрузки + всплывающая панель
├── managers_ui.py      # диалог менеджера
├── permissions.py      # диалог разрешений
├── usb_bridge.py       # WebUSB (SUBMITURB + DISCARDURB)
├── browser_page.py     # QWebEnginePage с инжектами
├── browser_window.py   # главное окно
└── js/
    ├── __init__.py
    ├── passwords.js          # автозаполнение
    └── webusb_shim.js        # шим navigator.usb
```

---

---

## О качестве кода

Этот проект — продукт **вайб-кодинга**. Что это значит на практике:

- **Написан совместно с LLM**, без предварительного
  проектирования. Сначала пробовали одно, потом другое, что-то
  откатывали, что-то оставляли. История коммитов это покажет.
- **Тестов нет.** Совсем. Есть только метод «запустил — работает».
- **Code review не было.** Единственный ревьюер — автор и его
  терпение.
- **Некоторые решения — костыли**, продиктованные не архитектурой,
  а «вот тут оно наконец заработало, не трогай».
- **Документация внутри кода минимальная**, только для самых
  неочевидных мест.

### Где особенно заметно

- **`usb_bridge.py`** — весь модуль построен на реверс-инжиниринге
  поведения Chrome через `strace`. Комментарии там — это не описание
  замысла, а описание того, что мы *увидели*. Часть кода может
  содержать магические числа, значение которых известно только
  конкретному набору ядро+libusb+Switch.
- **`js/passwords.js`** — SPA-логины обрабатываются через кучу
  эвристик: `MutationObserver`, `history.pushState` override,
  `sessionStorage` для запоминания username между экранами.
  Это работает, но легко ломается на новых сайтах.
- **`downloads.py`** — обход того, что Qt 6 переименовал
  `finished` в `stateChanged`, и что сигналы приходят в
  произвольном порядке.

### Что это значит для вас

**Если вы просто хотите запустить:** всё нормально, скорее всего
заработает. Проблемы — только у конкретных сайтов с WebUSB.

**Если хотите форкнуть и доработать:** добро пожаловать, но будьте
готовы, что некоторые места потребуется переписать. Не стесняйтесь
ломать существующие решения — многие из них не выдерживают
критики.

**Если хотите использовать в продакшене:** не надо. Возьмите
`qutebrowser`, `falkon` или соберите Chromium сами.

---

## Лицензия

[GPL-3.0](LICENSE).

## Благодарности

- [WebRCM][webrcm] — за сайт прошивки
- [fusee-launcher](https://github.com/ktemkin/fusee-launcher) — за
  понимание протокола Tegra RCM
- [Qt](https://www.qt.io/) и [Chromium](https://www.chromium.org/) — за движок
