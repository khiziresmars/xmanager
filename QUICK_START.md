# 🚀 XUI-Manager - Быстрый старт

## Загрузка в GitHub (однократно)

```bash
# 1. Создайте SSH ключ
ssh-keygen -t ed25519 -C "your@email.com" -f ~/.ssh/github_xui_manager
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/github_xui_manager

# 2. Покажите публичный ключ
cat ~/.ssh/github_xui_manager.pub
# Скопируйте вывод

# 3. Добавьте ключ на GitHub
# Откройте: https://github.com/settings/keys
# Нажмите "New SSH key" и вставьте ключ

# 4. Создайте приватный репозиторий на GitHub
# Откройте: https://github.com/new
# Имя: xui-manager
# Тип: Private
# НЕ создавайте README

# 5. Загрузите проект (замените YOUR_USERNAME)
cd /opt/xui-manager
git init
git add .
git commit -m "Initial commit: XUI-Manager v1.0"
git remote add origin git@github.com:YOUR_USERNAME/xui-manager.git
git branch -M main
git push -u origin main
```

## Установка на новом сервере

```bash
# 1. Создайте SSH ключ на новом сервере
ssh-keygen -t ed25519 -C "server2@example.com" -f ~/.ssh/github_xui_manager
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/github_xui_manager
cat ~/.ssh/github_xui_manager.pub  # Добавьте на GitHub

# 2. Клонируйте репозиторий (замените YOUR_USERNAME)
cd /opt
git clone git@github.com:YOUR_USERNAME/xui-manager.git

# 3. Запустите установку
cd xui-manager
sudo ./install.sh
```

Готово! Открой те: `https://your-domain.com/manager/`

## Обновление

```bash
cd /opt/xui-manager
sudo ./update.sh
```

## Внесение изменений

```bash
cd /opt/xui-manager

# Измените файлы...

git add .
git commit -m "Описание изменений"
git push origin main
```

---

**Подробная документация:** [GITHUB_SETUP.md](GITHUB_SETUP.md)
