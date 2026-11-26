# Configuración de Stripe

## Crear productos y precios

1. En Stripe Dashboard, activa el modo Test.
2. Crea un producto mensual, por ejemplo `OposNavarra Premium`.
3. Añade un precio recurrente de 29,95 EUR con facturación mensual.
4. Crea un cupón fijo de 28,95 EUR con duración de 1 mes para que el primer cobro sea 1 EUR.
5. Configura el Customer Portal con cancelación, cambios de plan y actualización de método de pago.

## Variables de entorno

Configura en `.env` o en el entorno del proceso:

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
STRIPE_FIRST_MONTH_COUPON_ID=coupon_...
FRONTEND_URL=http://localhost:5173
```

`STRIPE_FIRST_MONTH_COUPON_ID` es opcional. Si no se configura, el primer pago utiliza el precio completo de 29,95 EUR.

## Migraciones

```powershell
python manage.py migrate
```

## Stripe CLI

Instala Stripe CLI y autentícate:

```powershell
stripe login
stripe listen --forward-to localhost:8000/api/billing/webhook/
```

Copia el `whsec_...` mostrado por el comando en `STRIPE_WEBHOOK_SECRET`.

Prueba eventos concretos:

```powershell
stripe trigger checkout.session.completed
stripe trigger invoice.paid
stripe trigger invoice.payment_failed
stripe trigger customer.subscription.updated
stripe trigger customer.subscription.deleted
```

## Checkout y pruebas

1. Ejecuta Django y Vite.
2. Inicia sesión con el enlace mágico.
3. Abre `/premium-upgrade/` y pulsa `Activar Premium`.
4. Usa una tarjeta de prueba de Stripe, por ejemplo `4242 4242 4242 4242`.
5. Comprueba que `/payment/success` espera el webhook antes de mostrar Premium activo.
6. Cierra o cancela Checkout desde `/payment/cancel`.

Los webhooks son la fuente de activación. Nunca se concede acceso solo por llegar a la página de éxito.

## Customer Portal

Configura en Stripe Dashboard las opciones visibles del portal y una URL de retorno válida. El backend reutiliza `FRONTEND_URL/settings`.

## Tests

```powershell
$env:DATABASE_ENGINE="sqlite"
python manage.py test billing
```

## Pasar a producción

1. Sustituye todas las claves de test por las claves live.
2. Usa precios y cupones live equivalentes.
3. Crea un endpoint de webhook live apuntando a `https://tu-dominio/api/billing/webhook/`.
4. Configura `STRIPE_WEBHOOK_SECRET` con el secreto live.
5. Configura el frontend real en `FRONTEND_URL`, CORS y CSRF trusted origins.
6. Ejecuta migraciones y realiza pagos reales mínimos solo después de validar el entorno.
