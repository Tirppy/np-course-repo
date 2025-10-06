# Lab 1 HTTP File Server — Demonstration Report

## 1. Environment & Startup

Command executed:
```
docker compose up --build
```
![alt text](images/image-1.png)

## 2. Directory Structure Served
Base directory passed to server: `content/`

![alt text](images/image-2.png)

Short explanation: Contains required HTML, PNG, multiple PDFs, and nested directory.

## 3. Accessing the Root Directory
Open in browser:
```
http://localhost:8080/
```
![alt text](images/image-3.png)

## 4. Root HTML Page With Image Reference
Open:
```
http://localhost:8080/index.html
```
![alt text](images/image-4.png)

## 5. Nested Directory Listing
Navigate:
```
http://localhost:8080/books/
```
![alt text](images/image-5.png)

## 6. Downloading a PDF
Click `CSlab1.pdf` (or request directly):
```
http://localhost:8080/books/CSlab1.pdf
```
![alt text](images/image-6.png)

## 7. Client Usage (HTML Fetch)
Command:
```
python src\client.py localhost 8080 index.html
```
![alt text](images/image-7.png)

## 8. Client Usage (PDF Download)
Command:
```
python src\client.py localhost 8080 books/CSlab2.pdf
```
![alt text](images/image-8.png)
![alt text](images/image-9.png)

## 9. Client Usage (Directory Listing)
Command:
```
python src\client.py localhost 8080 books/
```
![alt text](images/image-10.png)

## 10. LAN Access Test (Optional Bonus)
From another device (replace with actual LAN IP):
```
python src\client.py 192.168.1.37 8080 index.html
```
![alt text](images/image-11.png)

## 11. Error Handling (404 Example)
Request unsupported or missing file:
```
http://localhost:8080/unknown.xyz
```
![alt text](images/image-12.png)

Or via client:
```
python src\client.py localhost 8080 unknown.xyz
```
![alt text](images/image-13.png)

## 12. Compliance Summary

- Docker & Compose: Implemented
- Single-request TCP server: Implemented
- File types: HTML, PNG, PDF served
- 404 behavior: Correct for missing/unsupported
- Directory listing: Implemented (nested)
- Subdirectory with PDFs/PNG: Present (`books/`)
- Client: Implements required CLI format; prints HTML, saves PNG/PDF
- Image referenced via <img>: Present in index.html
- Bonus (LAN browsing): Possible; steps documented

## 13. How to Stop
```
CTRL+C

docker compose down
```
![alt text](images/image-14.png)

## 14. Notes / Design Choices
- Only required extensions are served; others 404 for clarity.
- Path traversal guarded by normalized path prefix check.
- Minimal standard library only (no external dependencies).

---
End of Report.
