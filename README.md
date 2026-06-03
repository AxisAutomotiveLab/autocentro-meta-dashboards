# autocentro-meta-dashboards

Meta Ads dashboards para los 5 dealers de Autocentro PR.  
**Auto-actualiza cada 24h** vía GitHub Actions. Sin token en el browser. Sin errores 429.

## Dealers incluidos

| Dashboard | Cuenta Meta | ID |
|---|---|---|
| Autocentro Nissan | act_407938286956756 | [nissan.html] |
| Autocentro Chrysler | act_766659464282943 | [chrysler.html] |
| Autocentro Mas | act_850818032362895 | [mas.html] |
| Autocentro Más Guaynabo | act_1186750509063901 | [guaynabo.html] |
| Autocentro Toyota | act_277757027036799 | [toyota.html] |

---

## ⚡ Setup — 4 pasos (una sola vez)

### Paso 1 — Generar tu Meta Access Token

1. Ve a [developers.facebook.com/tools/explorer](https://developers.facebook.com/tools/explorer)
2. Selecciona tu **App** (la de Autocentro PR)
3. En **User or Page** selecciona tu usuario
4. Agrega estos permisos:
   - `ads_read`
   - `ads_management`  
   - `business_management`
5. Haz clic en **Generate Access Token**
6. Copia el token (empieza con `EAA...`)

> ⚠️ Este token dura ~60 días. Cuando expire, repite este paso y actualiza el Secret en GitHub.

---

### Paso 2 — Guardar el token en GitHub Secrets

1. Ve a tu repo en GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Haz clic en **New repository secret**
3. Nombre: `META_ACCESS_TOKEN`
4. Valor: pega el token `EAA...` que generaste
5. Haz clic en **Add secret**

---

### Paso 3 — Correr el GitHub Action por primera vez

1. Ve a tu repo → pestaña **Actions**
2. Haz clic en **Fetch Meta Ads Data** en el panel izquierdo
3. Haz clic en **Run workflow** → **Run workflow** (botón verde)
4. Espera ~2 minutos mientras corre
5. Verifica que aparezcan los archivos en `/data/`:
   - `nissan_data.json`
   - `chrysler_data.json`
   - `mas_data.json`
   - `guaynabo_data.json`
   - `toyota_data.json`

---

### Paso 4 — Activar GitHub Pages

1. Ve a tu repo → **Settings** → **Pages**
2. En **Source** selecciona: `Deploy from a branch`
3. Branch: `main` / Folder: `/ (root)`
4. Haz clic en **Save**
5. Espera 1-2 minutos
6. Tu URL será: `https://TU_USUARIO.github.io/autocentro-meta-dashboards/`

---

## 🔄 Cómo funciona el auto-update

```
GitHub Actions (6:00 AM UTC / 2:00 AM PR Time)
    ↓
fetch_data.py llama Meta Marketing API con META_ACCESS_TOKEN
    ↓
Genera: data/nissan_data.json, chrysler_data.json, etc.
    ↓
Auto-commit al repo
    ↓
GitHub Pages sirve los HTMLs actualizados
    ↓
Abres el dashboard → lee el JSON → sin token, sin 429
```

## 🔑 Renovar el token (cada ~60 días)

1. Genera nuevo token en Graph Explorer (Paso 1)
2. Ve a GitHub → Settings → Secrets → `META_ACCESS_TOKEN` → Update secret
3. Listo — el próximo Action run usará el nuevo token

## 📁 Estructura

```
autocentro-meta-dashboards/
├── .github/
│   └── workflows/
│       └── fetch-meta-data.yml   ← corre cada 24h
├── data/
│   ├── nissan_data.json          ← generado por el Action
│   ├── chrysler_data.json
│   ├── mas_data.json
│   ├── guaynabo_data.json
│   └── toyota_data.json
├── index.html                    ← hub principal
├── nissan.html
├── chrysler.html
├── mas.html
├── guaynabo.html
├── toyota.html
└── fetch_data.py                 ← script de fetch
```
