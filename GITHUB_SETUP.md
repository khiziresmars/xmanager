# 🚀 Настройка GitHub для XUI-Manager

Пошаговая инструкция по загрузке проекта в приватный GitHub репозиторий и установке на других серверах.

---

## 📋 Оглавление

1. [Создание SSH ключа](#1-создание-ssh-ключа)
2. [Добавление ключа в GitHub](#2-добавление-ключа-в-github)
3. [Создание репозитория на GitHub](#3-создание-репозитория-на-github)
4. [Загрузка проекта в GitHub](#4-загрузка-проекта-в-github)
5. [Установка на новых серверах](#5-установка-на-новых-серверах)
6. [Обновление проекта](#6-обновление-проекта)

---

## 1. Создание SSH ключа

SSH ключ нужен для безопасного доступа к приватному репозиторию GitHub.

### На текущем сервере:

```bash
# Генерация SSH ключа
ssh-keygen -t ed25519 -C "your_email@example.com" -f ~/.ssh/github_xui_manager

# Нажмите Enter для всех вопросов (оставьте пустой passphrase для автоматизации)

# Добавление ключа в SSH agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/github_xui_manager

# Просмотр публичного ключа
cat ~/.ssh/github_xui_manager.pub
```

**Скопируйте весь вывод команды** (начинается с `ssh-ed25519` и заканчивается вашим email).

---

## 2. Добавление ключа в GitHub

### Шаги:

1. Откройте GitHub: https://github.com
2. Нажмите на ваш аватар (правый верхний угол) → **Settings**
3. В левом меню: **SSH and GPG keys**
4. Нажмите **New SSH key**
5. Заполните:
   - **Title**: `XUI-Manager Server` (или любое имя)
   - **Key type**: `Authentication Key`
   - **Key**: Вставьте скопированный публичный ключ
6. Нажмите **Add SSH key**
7. Подтвердите пароль GitHub

### Проверка подключения:

```bash
# Проверка SSH соединения с GitHub
ssh -T git@github.com

# Должно вывести:
# Hi username! You've successfully authenticated, but GitHub does not provide shell access.
```

---

## 3. Создание репозитория на GitHub

### Способ 1: Через веб-интерфейс

1. Откройте: https://github.com/new
2. Заполните:
   - **Repository name**: `xui-manager`
   - **Description**: `Управление пользователями 3x-ui через REST API`
   - **Visibility**: ✅ **Private** (приватный репозиторий)
   - ❌ НЕ выбирайте "Initialize this repository with a README"
3. Нажмите **Create repository**

### Способ 2: Через GitHub CLI (если установлен)

```bash
gh repo create xui-manager --private --description "Управление пользователями 3x-ui"
```

### Скопируйте SSH URL:

После создания GitHub покажет страницу с инструкциями. Найдите SSH URL:
```
git@github.com:ВАШ_USERNAME/xui-manager.git
```

---

## 4. Загрузка проекта в GitHub

### Вернитесь на сервер и выполните:

```bash
cd /opt/xui-manager

# Инициализация Git репозитория
git init

# Добавление всех файлов
git add .

# Первый коммит
git commit -m "Initial commit: XUI-Manager v1.0

- REST API для управления пользователями 3x-ui
- Веб-интерфейс с темной темой
- Пагинация пользователей
- Автоматическая синхронизация данных
- Массовые операции
- Установочный и обновляющий скрипты"

# Добавление remote репозитория (замените YOUR_USERNAME)
git remote add origin git@github.com:YOUR_USERNAME/xui-manager.git

# Переименование ветки в main (если нужно)
git branch -M main

# Отправка в GitHub
git push -u origin main
```

### Проверка:

Откройте в браузере: `https://github.com/YOUR_USERNAME/xui-manager`

Вы должны увидеть все файлы проекта! 🎉

---

## 5. Установка на новых серверах

Теперь вы можете легко установить XUI-Manager на любой сервер с 3x-ui.

### Шаг 1: Создание SSH ключа на новом сервере

```bash
# На НОВОМ сервере
ssh-keygen -t ed25519 -C "server2@example.com" -f ~/.ssh/github_xui_manager
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/github_xui_manager
cat ~/.ssh/github_xui_manager.pub
```

### Шаг 2: Добавление ключа в GitHub

- Повторите шаги из раздела 2
- Используйте другое имя, например: `XUI-Manager Server 2`

### Шаг 3: Клонирование и установка

```bash
# Клонирование приватного репозитория
cd /opt
git clone git@github.com:YOUR_USERNAME/xui-manager.git

# Запуск установки
cd xui-manager
chmod +x install.sh
sudo ./install.sh
```

**Скрипт автоматически:**
- ✅ Найдет установленный 3x-ui
- ✅ Установит все зависимости
- ✅ Настроит systemd сервис
- ✅ Настроит Nginx
- ✅ Предложит получить SSL сертификат

### Результат:

```
✅ XUI-Manager успешно установлен!

🌐 X-UI панель:     https://your-domain.com/esmars/
💻 XUI-Manager:     https://your-domain.com/manager/
📚 API документация: https://your-domain.com/manager/api/docs
```

---

## 6. Обновление проекта

### Внесение изменений на основном сервере:

```bash
cd /opt/xui-manager

# Внесите изменения в файлы...

# Проверка изменений
git status
git diff

# Добавление изменений
git add .

# Коммит
git commit -m "Описание изменений"

# Отправка в GitHub
git push origin main
```

### Обновление на других серверах:

```bash
cd /opt/xui-manager

# Просто запустите скрипт обновления
sudo ./update.sh
```

**Скрипт автоматически:**
- ✅ Сохранит вашу конфигурацию (.env)
- ✅ Создаст резервную копию БД
- ✅ Загрузит обновления из GitHub
- ✅ Обновит зависимости
- ✅ Перезапустит сервис

---

## 🔐 Безопасность

### Рекомендации:

1. **Используйте приватный репозиторий** - ваши конфиденциальные данные не будут публичными

2. **Не коммитьте .env файл** - уже добавлен в .gitignore, но проверьте:
   ```bash
   git ls-files | grep .env
   # Не должно ничего вывести
   ```

3. **Регулярно обновляйте SSH ключи** - меняйте ключи раз в 6-12 месяцев

4. **Используйте разные ключи** для разных серверов (опционально)

5. **Удаление доступа** - если сервер скомпрометирован:
   - GitHub → Settings → SSH keys → Delete нужный ключ

---

## 🔧 Полезные Git команды

```bash
# Просмотр истории
git log --oneline -10

# Откат к предыдущей версии
git reset --hard HEAD~1

# Просмотр удаленного репозитория
git remote -v

# Создание новой ветки для экспериментов
git checkout -b feature/new-feature

# Переключение между ветками
git checkout main

# Слияние веток
git merge feature/new-feature

# Просмотр всех веток
git branch -a

# Удаление ветки
git branch -d feature/new-feature
```

---

## ❓ Решение проблем

### Ошибка: "Permission denied (publickey)"

**Причина**: SSH ключ не добавлен в GitHub или не загружен в SSH agent

**Решение**:
```bash
ssh-add ~/.ssh/github_xui_manager
ssh -T git@github.com
```

### Ошибка: "fatal: remote origin already exists"

**Решение**:
```bash
git remote remove origin
git remote add origin git@github.com:YOUR_USERNAME/xui-manager.git
```

### Ошибка: "Updates were rejected because the remote contains work"

**Решение**:
```bash
git pull origin main --rebase
git push origin main
```

### Забыли добавить файл в .gitignore

**Решение**:
```bash
# Удаление из Git (но не с диска)
git rm --cached путь/к/файлу

# Добавление в .gitignore
echo "путь/к/файлу" >> .gitignore

# Коммит
git commit -m "Remove sensitive file from Git"
git push origin main
```

---

## 📚 Дополнительные ресурсы

- **Git документация**: https://git-scm.com/doc
- **GitHub SSH ключи**: https://docs.github.com/en/authentication/connecting-to-github-with-ssh
- **GitHub CLI**: https://cli.github.com/
- **Git cheat sheet**: https://education.github.com/git-cheat-sheet-education.pdf

---

## 🎯 Быстрый старт (TL;DR)

### На текущем сервере:

```bash
# 1. Создать SSH ключ
ssh-keygen -t ed25519 -C "your@email.com" -f ~/.ssh/github_xui_manager
cat ~/.ssh/github_xui_manager.pub  # Скопировать вывод

# 2. Добавить ключ на GitHub.com → Settings → SSH keys

# 3. Создать репозиторий на github.com/new (private)

# 4. Загрузить проект
cd /opt/xui-manager
git init
git add .
git commit -m "Initial commit"
git remote add origin git@github.com:YOUR_USERNAME/xui-manager.git
git push -u origin main
```

### На новом сервере:

```bash
# 1. Создать SSH ключ (повторить шаги выше)

# 2. Клонировать и установить
cd /opt
git clone git@github.com:YOUR_USERNAME/xui-manager.git
cd xui-manager
sudo ./install.sh
```

### Обновление:

```bash
cd /opt/xui-manager
sudo ./update.sh
```

---

**Готово!** Теперь ваш проект в безопасном приватном репозитории и может быть легко установлен на любой сервер. 🎉
