# **TECH STACK**
**Excel Generator**

**PPL \- C7**

---

# **1\. Ringkasan Eksekutif**

Dokumen ini menguraikan *tech stack* yang diimplementasikan dalam pengembangan aplikasi Excel Generator. Pemilihan teknologi didasarkan pada penguasaan teknis tim, ekosistem *library* yang kaya, serta tuntutan performa tinggi dalam pemrosesan data secara efisien.

| Django (Backend) | Next.js (Frontend) | PostgreSQL (Database) |
| :---: | :---: | :---: |

# **2\. Latar Belakang Pemilihan Stack**

## **2.1 Backend (Django)**

Pemilihan Django sebagai kerangka kerja *backend* didasarkan pada beberapa pertimbangan strategis yang selaras dengan tujuan efisiensi dan skalabilitas proyek:

1. **Efisiensi Pengembangan & Produktivitas Tim**  
   Pemanfaatan ekosistem Python yang sudah dikuasai oleh tim meminimalisir *learning curve*. Hal ini memungkinkan proses pengembangan berlangsung lebih cepat sehingga tim dapat langsung fokus pada logika bisnis inti sejak tahap awal proyek.

2. **Ekosistem Library Pemrosesan Data yang Komprehensif**  
   Python memiliki dukungan pustaka (*library*) yang sangat luas dan matang untuk manipulasi berbagai format dokumen.

3. **Arsitektur API yang Robust dengan Django REST Framework (DRF)**   
   Penggunaan DRF mempermudah pembangunan API yang terstruktur, aman, dan mudah didokumentasikan. Hal ini memastikan integrasi antara *frontend* dan *backend* berjalan dengan lancar serta memudahkan pengembangan fitur di masa depan.

## **2.2 Next.js**

Next.js dipilih sebagai kerangka kerja *frontend* utama untuk menghadirkan antarmuka yang responsif, cepat, dan mudah dipelihara. Pemilihan ini didasarkan pada keunggulan teknis berikut:

1. **Ekosistem Berbasis React yang Luas**  
   Memanfaatkan basis React yang matang, tim dapat mengakses ekosistem komponen UI yang sangat besar. Hal ini mempercepat proses pembangunan antarmuka (UI) tanpa harus membangun segalanya dari nol.  
2. **Strategi Rendering Fleksibel (SSR & SSG)**  
   Dukungan *Server-Side Rendering* (SSR) dan *Static Site Generation* (SSG) memungkinkan aplikasi menyajikan konten dengan lebih cepat, meningkatkan performa di sisi klien, serta memberikan optimasi SEO yang lebih baik.  
3. **Struktur Routing Intuitif**  
   Sistem *file-based routing* yang dimiliki Next.js memudahkan pengelolaan navigasi aplikasi secara logis dan terorganisir, sehingga meminimalisir kompleksitas kode saat skala aplikasi bertambah besar.  
4. **Kapabilitas API Routes**  
   Fitur *API Routes* memungkinkan eksekusi logika ringan di sisi *serverless* tanpa memerlukan infrastruktur *backend* terpisah untuk tugas-tugas sederhana, sehingga arsitektur menjadi lebih ramping.  
5. **Keamanan Kode dengan TypeScript**  
   Dukungan bawaan untuk TypeScript memastikan deteksi kesalahan lebih dini selama proses pengembangan (*type-safety*), menghasilkan basis kode yang lebih stabil dan mudah di *debug*.

# **3\. Arsitektur Sistem**

Aplikasi ini menggunakan arsitektur client-server dengan pemisahan yang jelas antara frontend dan backend. File conversion yang berat ditangani secara asynchronous menggunakan task queue.

| Layer | Teknologi | Peran |
| ----- | ----- | ----- |
| Frontend | Next.js 14+ | UI, upload *file*, tampilkan hasil konversi, menampilkan riwayat |
| Backend API | Django \+ DRF | REST API, validasi, logika konversi |
| Database | PostgreSQL | Simpan metadata *file*, riwayat konversi, user |
| File Storage | VM File System | Simpan *file* upload dan hasil konversi |

# **4\. Backend \- Django**

## **4.1 Spesifikasi Teknis**

| Komponen | Teknologi / Versi | Keterangan |
| ----- | ----- | ----- |
| Framework | Django 6.0.3 | Web framework utama |
| API Layer | Django REST Framework 3.16.1 | Pembuatan REST API |
| ORM / Database | Django ORM \+ PostgreSQL | Manajemen data |

## **4.2 Library Konversi File** 

| Library | Format Input | Fungsi |
| ----- | ----- | ----- |
| pdfplumber | PDF | Ekstraksi tabel dan teks dari PDF terstruktur |
| PyPDF2 | PDF | Validasi PDF |
| openpyxl | XLSX, XLS | Baca & tulis file Excel modern |
| xlrd | XLS | Baca file Excel lama (.xls) |
| pytesseract | Gambar scan | OCR untuk file gambar / PDF scan |

## **4.3 Struktur Direktori Backend**

backend/  
├── api/                        \# Modul yang menangani endpoint API publik  
├── file\_processing/    \# Modul untuk pemrosesan file: ekstraksi teks  
├── llm/                       \# Modul integrasi LLM: ekstraksi struktur data, validasi hasil, dan reasoning pipeline  
├── config/                  \# Konfigurasi inti aplikasi Django (settings, URL routing, WSGI/ASGI)  
└── requirements.txt   \# Daftar dependensi Python yang digunakan oleh backend

# **5\. Frontend \- Next.js**

## **5.1 Spesifikasi Teknis**

| Komponen | Teknologi / Versi | Keterangan |
| ----- | ----- | ----- |
| Framework | Next.js 16+ (App Router) | Framework React dengan SSR/SSG |
| Language | TypeScript | Type safety untuk kode lebih robust |
| Styling | Tailwind CSS | Utility-first CSS framework |
| HTTP Client | Fetch API | Komunikasi ke Django API |
| File Upload | React DragEvent | Drag & drop upload experience |