# sub-indir 🎬

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**sub-indir**, yabancı dizi ve filmler için **yalnızca Türkçe altyazılara odaklanan**, Subliminal alternatifi modern ve akıllı bir komut satırı (CLI) aracıdır.

Türkiye'deki en zengin ve güncel altyazı kaynağı olan **TurkceAltyazi.org** üzerinden doğrudan arama ve indirme yapar. Video dosyanızın release grubunu (`FLUX`, `RARBG`, `PSA`, `YTS` vb.) analiz ederek **senkronize altyazıyı** otomatik eşler ve eski kodlamalı altyazıları (`Windows-1254` / `ISO-8859-9`) kayıpsız şekilde **UTF-8'e** dönüştürür.

---

## 🎯 Neden sub-indir?

| Özellik | Subliminal / Diğer Araçlar | **sub-indir** |
| :--- | :---: | :---: |
| **TurkceAltyazi.org Desteği** | ❌ Yok |  **Var (Doğrudan & Ücretsiz)** |
| **Türkçe Odaklılık** | ⚠️ Global (TR çeviriler genelde eksik) |  **%100 Türkçe Odaklı** |
| **Karakter Kodlaması (Encoding)** | ⚠️ Sık sık bozuk karakterler (`ş, ğ, ı`) |  **Otomatik Kusursuz UTF-8** |
| **Release Grubu Eşleştirme** | ⚠️ Sadece hash / kısıtlı regex |  **`guessit` ile %99 Doğruluk** |
| **Arşiv (.zip) Yönetimi** | ⚠️ Bazen elle açmak gerekir |  **Otomatik Açıp İsimlendirir** |
| **Arayüz (CLI UX)** | ⚪ Basit terminal çıktısı |  **Renkli Tablolar & İnteraktif Menü** |

---

## 📦 Kurulum (Installation)

Sisteminizde Python 3.9 veya daha yeni bir sürümün yüklü olduğundan emin olun.

### 🪟 Windows İçin Kurulum

#### Yöntem 1: Doğrudan Git Reposundan (Tavsiye Edilen)
Terminali (PowerShell veya CMD) açın ve projeyi kurun:

```powershell
# 1. Repoyu klonlayın
git clone https://github.com/fatihozturk-1/sub-indir.git
cd sub-indir

# 2. Sistem genelinde (Global) CLI olarak kurun
python -m pip install -e .
```
> [!TIP]
> Kurulum tamamlandığında artık herhangi bir sanal ortam açmanıza gerek kalmadan bilgisayarınızın her yerinden doğrudan `sub-indir` komutunu çalıştırabilirsiniz.

---

### 🐧 Linux (Ubuntu / Debian / Arch / Fedora) İçin Kurulum

Modern Linux dağıtımlarında (PEP 668 - Externally Managed Environment) CLI araçlarını izole çalıştırmak için en temiz yöntem **`pipx`** veya kullanıcı dizinine (`--user`) kurmaktır:

#### Yöntem A: `pipx` ile Kurulum (En Temiz Yol)
```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y python3-pip pipx git
pipx ensurepath

# Arch Linux
sudo pacman -S python-pipx git
pipx ensurepath

# Repoyu klonlayıp kurun
git clone https://github.com/fatihozturk-1/sub-indir.git
cd sub-indir
pipx install .
```

#### Yöntem B: Standart `pip` ile Kurulum
```bash
git clone https://github.com/fatihozturk-1/sub-indir.git
cd sub-indir

# Kullanıcı ortamına kurun
python3 -m pip install --user -e .
```
*(Eğer `~/.local/bin` PATH'inizde değilse `export PATH="$HOME/.local/bin:$PATH"` ekleyin).*

---

## 🚀 Kullanım (Usage)

Herhangi bir terminal penceresinde filmlerinizin/dizilerinizin olduğu dizine gidin:

### 1. Bulunulan Dizindeki Tüm Videoları Tarama (Subliminal Benzeri)
Klasördeki tüm video dosyalarını tarar ve eksik Türkçe altyazıları otomatik indirir:
```bash
sub-indir download .
```
*(Not: `.` yazmasanız bile varsayılan olarak bulunulan klasör taranır: `sub-indir download`)*

### 2. Otomatik Mod (`-a` / `--auto`)
Kullanıcıya sormadan en yüksek puanlı (en uyumlu) altyazıyı otomatik seçip indirir:
```bash
sub-indir download . -a
```

### 3. Alt Klasörleri de Taramak İçin (`-r` / `--recursive`)
Dizi arşivlerinizde sezon klasörleri (`Dizi/Sezon 1/...`) varsa alt klasörleri de derinlemesine tarar:
```bash
sub-indir download . -a -r
```

### 4. Tek Bir Video Dosyası İçin İndirme
```bash
# İnteraktif seçim menüsüyle
sub-indir download "Severance.S02E01.1080p.WEB.H264-FLUX.mkv"

# Otomatik en iyi eşleşmeyi indir
sub-indir download "Inception.2010.1080p.BluRay.x264-REFiNED.mkv" -a
```

### 5. Başka Bir Klasörü Belirterek Tarama
```bash
sub-indir download "D:\Filmler" -a
# Linux için:
sub-indir download "/media/hdd/filmler" -a
```

---

## ⚙️ Parametreler ve Seçenekler

| Parametre | Kısayol | Açıklama |
| :--- | :---: | :--- |
| `target` | *(Argüman)* | Taranacak klasör, dosya yolu veya film adı. (Varsayılan: `.`) |
| `--auto` | `-a` | Soru sormadan en yüksek puanlı eşleşmeyi otomatik indirir. |
| `--recursive` | `-r` | Klasör belirtildiğinde alt klasörleri de derinlemesine tarar. |
| `--force` | `-f` | Altyazı dosyası zaten mevcut olsa bile tekrar indirip üzerine yazar. |
| `--no-suffix` | | `video.tr.srt` yerine doğrudan `video.srt` olarak kaydeder. |
| `--help` | | Yardım mesajını ve kullanım detaylarını gösterir. |

---

## 🔑 OpenSubtitles Desteği (Opsiyonel)

TurkceAltyazi.org herhangi bir API anahtarı veya üyelik gerektirmez ve doğrudan çalışır. 

Dilerseniz ek kaynak olarak **OpenSubtitles.com** v3 REST API'sini de kullanabilirsiniz. [OpenSubtitles.com](https://www.opensubtitles.com)'dan ücretsiz aldığınız API anahtarını ortam değişkeni olarak tanımlamanız yeterlidir:

```bash
# Linux / macOS (Bash / Zsh):
export OPENSUBTITLES_API_KEY="anahtariniz"

# Windows (PowerShell):
$env:OPENSUBTITLES_API_KEY="anahtariniz"

# Windows (CMD):
set OPENSUBTITLES_API_KEY=anahtariniz
```

---

## 🛠 Katkıda Bulunma

1. Bu depoyu Fork edin.
2. Yeni özellik için branch açın (`git checkout -b feature/yeni-ozellik`).
3. Değişikliklerinizi commit edin (`git commit -m 'feat: Yeni özellik eklendi'`).
4. Branch'inizi push edin (`git push origin feature/yeni-ozellik`).
5. Bir Pull Request (PR) oluşturun.

