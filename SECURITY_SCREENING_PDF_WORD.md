# Security Screening PDF/Word Validation

Dokumen ini untuk kebutuhan penilaian keamanan dengan ruang lingkup sempit: validasi upload PDF/Word.
Tujuannya menunjukkan bahwa sistem menolak file berbahaya/manipulatif dan tetap menerima file valid.

## 1. Scope Screening

- Endpoint: `POST /upload/`
- Tipe file: `.pdf`, `.doc`, `.docx`
- Fokus kontrol:
  - MIME/extension mismatch
  - Struktur file rusak
  - File terenkripsi/password-protected
  - Bypass batas halaman (`>100` halaman)

## 2. Tools Yang Dipakai

- `pytest` untuk bukti automated test (security regression test).
- `curl` + script screening untuk simulasi upload real ke API.
- `Bandit` (opsional) untuk static security check di kode Python.
- Tools "sejenis Metasploit" yang aman untuk web/API:
  - OWASP ZAP baseline scan (opsional, non-intrusive)
  - Nuclei template scan (opsional)

Catatan: untuk scope validasi dokumen, PoC upload berbasis file crafted lebih relevan dibanding eksploitasi framework umum.

## 3. Jalankan Screening End-to-End

Pastikan backend sudah jalan di `http://127.0.0.1:8000`.

### 3.1. Automated test khusus security

```bash
cd backend
python3 -m pytest file_processing/tests/test_security_screening_pdf_word.py -q
```

### 3.2. Dynamic screening ke endpoint upload

```bash
cd ..
chmod +x scripts/security-screening-pdf-word.sh
./scripts/security-screening-pdf-word.sh http://127.0.0.1:8000
```

Script akan otomatis membuat sample file berikut dan menguji response API:
- DOCX palsu (plaintext rename `.docx`) -> harus ditolak.
- DOCX terenkripsi (OLE wrapper) -> harus ditolak sebagai password-protected.
- PDF corrupt -> harus ditolak.
- DOC dengan marker halaman >100 -> harus ditolak.
- DOCX valid minimal -> harus diterima.

### 3.3. Static analysis (opsional, nilai tambah)

```bash
cd backend
python3 -m pip install bandit
python3 -m bandit -r file_processing/services -ll
```

### 3.4. API baseline scan (opsional, nilai tambah)

Contoh OWASP ZAP baseline (safe/passive mode):

```bash
docker run --rm -t \
  -v "$PWD":/zap/wrk:rw \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py -t http://host.docker.internal:8000 -r zap-report.html
```

## 4. Bukti Yang Perlu Dimasukkan Ke Laporan

- Screenshot output `pytest` test security khusus.
- Screenshot output script `security-screening-pdf-word.sh` (PASS/FAIL tiap skenario).
- Jika pakai Bandit/ZAP: ringkas temuan dan status perbaikan.

Gunakan format ringkas berikut:

1. Tujuan screening.
2. Scope endpoint/file type.
3. Skenario serangan yang diuji.
4. Hasil aktual vs expected.
5. Kesimpulan risiko residual dan rekomendasi hardening.

## 5. Acceptance Criteria (Untuk Nilai)

- Minimal 4 skenario serangan tervalidasi ditolak sistem.
- Ada 1 skenario file valid yang lolos (untuk bukti tidak over-blocking).
- Hasil bisa direproduksi via command.
- Ada dokumentasi hasil + bukti output.