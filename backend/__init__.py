"""
Настройки окружения для моделей. Файл выполняется раньше любого модуля backend, а значит и раньше
импорта Paddle / transformers, поэтому переменные успевают подействовать.

    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK  PaddleX перед запуском ходит в сеть проверять источники моделей: отключаем.
    OFFLINE=1                              запрет любых обращений к Hugging Face (HF_HUB_OFFLINE, TRANSFORMERS_OFFLINE).
                                           Включать только когда модели уже скачаны (см. README, «Работа без сети»).
"""
import os

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

if os.getenv("OFFLINE") == "1":
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
