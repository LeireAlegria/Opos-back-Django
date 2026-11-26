# Backend de OposNavarra

API inicial en Django con PostgreSQL local y SQLite opcional para pruebas.
El catálogo de demostración no es contenido oficial ni revisado.

## Requisitos

- Python 3.12 o posterior compatible con la versión instalada de Django.
- PostgreSQL local (o configura SQLite para desarrollo/pruebas).

## Puesta en marcha con PostgreSQL

1. Crea la base de datos `oposnavarra` en PostgreSQL.
2. Usa `.env.example` como referencia y configura las variables en PowerShell
   (Django no carga archivos `.env` automáticamente):

   ```powershell
   $env:DATABASE_USER = "postgres"
   $env:DATABASE_PASSWORD = "tu-clave-local"
   $env:DJANGO_SECRET_KEY = "una-clave-local"
   $env:DJANGO_DEBUG = "true"
   ```

3. Instala y prepara el proyecto:

   `createsuperuser` crea una cuenta nueva; no necesitas tener un usuario
   registrado previamente. Te pedirá el nombre de usuario, correo y contraseña
   que quieras usar para entrar en `/admin/`.

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python manage.py migrate
   python manage.py load_demo_catalog
   python manage.py createsuperuser
   python manage.py runserver
   ```

Para SQLite local o para ejecutar las pruebas, establece
`$env:DATABASE_ENGINE = "sqlite"` antes de `migrate`/`test`.

## API

- `GET /api/oppositions?page=1&pageSize=10&search=celador&category=sanidad`
- `GET /api/oppositions/{slug}`
- `GET /api/oppositions/{oppositionSlug}/topics/{topicSlug}/questions`
- `GET /api/csrf`
- `POST /api/oppositions/{oppositionSlug}/topics/{topicSlug}/questions/{questionSlug}/reports`

La lista devuelve `items`, `page`, `pageSize` y `totalItems`. Las fichas incluyen
categoría, temas, configuración de práctica y `contentReviewedAt`. Una modalidad
sin configuración devuelve `null`; el catálogo puede administrarse desde Django
Admin en `/admin/`.

La ruta de preguntas devuelve cinco preguntas aleatorias del tema, sus opciones
de respuesta y una duración de cinco minutos. No incluye las respuestas
correctas. Si el tema no tiene cinco preguntas cargadas, responde con HTTP 409.
Para reportar una pregunta, el cliente obtiene primero el token en `/api/csrf` y
lo envía en la cabecera `X-CSRFToken` del `POST`, junto con un motivo y un
comentario opcional. Los reportes pendientes se pueden revisar desde Django
Admin.

En el panel, busca oposiciones por nombre, filtra por categoría o estado y edita
el número de preguntas y la publicación directamente desde el listado. Al abrir
una oposición, puedes gestionar sus temas y modalidades de práctica en la misma
pantalla. Las acciones de activación permiten publicar u ocultar varias
oposiciones a la vez. El panel incluye estilos propios; para que Django sirva el
CSS durante el desarrollo, inicia `runserver` con
`$env:DJANGO_DEBUG = "true"` en esa misma terminal.

Las variables `CORS_ALLOWED_ORIGINS` y `CSRF_TRUSTED_ORIGINS` configuran los
orígenes permitidos para la API; por defecto se permite el servidor de desarrollo
de Vite en `http://localhost:5173` y `http://127.0.0.1:5173`.

Las rutas de autenticación, intentos y pagos quedan fuera de este alcance: su
contrato depende de decisiones pendientes recogidas en
[`BACKEND_API_PLAN.md`](../boostrat-front/BACKEND_API_PLAN.md).
