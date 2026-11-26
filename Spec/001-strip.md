# Implementación de Stripe Checkout en mi proyecto

Quiero integrar Stripe en mi aplicación, cuyo backend está desarrollado con Python y Django.

Quiero utilizar **Stripe Hosted Checkout**, de manera que cuando el usuario pulse el botón de contratar o pagar, sea redirigido a una página externa alojada en `checkout.stripe.com`, donde Stripe se encargará de gestionar el proceso de pago.

No quiero implementar un formulario propio para introducir los datos de la tarjeta.

## 1. Analizar el proyecto existente

Antes de modificar código:

- Analiza la arquitectura actual del backend y del frontend.
- Identifica el sistema de autenticación.
- Revisa los modelos de usuarios, planes, suscripciones y permisos existentes.
- Identifica cómo se gestionan las variables de entorno.
- Reutiliza los componentes existentes siempre que sea posible.
- Comprueba si el modelo de negocio utiliza suscripciones recurrentes o pagos únicos.
- Evita modificar funcionalidades que no estén relacionadas con la integración.

## 2. Configurar Stripe

- Instala el SDK oficial de Stripe para Python.
- Añade la dependencia al archivo de dependencias del proyecto.
- Configura las siguientes variables de entorno:

```env
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_ID=
FRONTEND_URL=
```

- Añade las variables necesarias al `.env.example`.
- Nunca expongas las claves privadas en el frontend ni las subas al repositorio.
- Utiliza inicialmente el entorno de pruebas de Stripe.
- Si existen varios planes, configura la correspondencia entre los planes internos y los identificadores de precios de Stripe.

## 3. Arquitectura del backend

Si encaja con la arquitectura existente, crea una aplicación Django llamada `billing` con la siguiente estructura:

```text
billing/
    models.py
    views.py
    services.py
    webhooks.py
    urls.py
    admin.py
    tests.py
```

Separa la lógica de negocio, la comunicación con Stripe y los endpoints HTTP.

## 4. Modelos de base de datos

Crea o adapta los modelos existentes para almacenar:

- Usuario o entidad propietaria de la suscripción.
- Stripe Customer ID.
- Stripe Subscription ID.
- Stripe Price ID.
- Plan contratado.
- Estado de la suscripción.
- Fecha de finalización del periodo contratado.
- Cancelación al finalizar el periodo.
- Fecha de creación y actualización.

Añade las restricciones de unicidad necesarias y genera las migraciones correspondientes.

Stripe será la fuente de referencia para la facturación y Django gestionará los permisos de acceso.

## 5. Crear el endpoint de Checkout

Implementa un endpoint autenticado:

`POST /api/billing/checkout/`

Este endpoint debe:

1. Identificar al usuario autenticado.
2. Validar el plan seleccionado.
3. Obtener el precio de Stripe desde una configuración controlada por el backend.
4. Crear o reutilizar el Stripe Customer asociado al usuario.
5. Comprobar que no se generen suscripciones duplicadas.
6. Crear una Checkout Session mediante la API oficial de Stripe.
7. Utilizar `mode="subscription"` para suscripciones o `mode="payment"` para pagos únicos.
8. Asociar la sesión con el usuario mediante `client_reference_id` y metadata.
9. Configurar las URLs de éxito y cancelación.
10. Devolver la URL de Checkout al frontend.

La respuesta debe tener este formato:

```json
{
    "url": "https://checkout.stripe.com/..."
}
```

No aceptar importes arbitrarios enviados desde el frontend.

## 6. Integración con el frontend

Localiza los botones existentes de contratación o pago.

Al pulsar uno de ellos:

- Realiza una petición al endpoint de Checkout.
- Muestra un estado de carga.
- Evita que el usuario pulse repetidamente el botón.
- Gestiona los posibles errores.
- Redirige al usuario mediante `window.location.href` a la URL devuelta por Stripe.

Mantén el diseño y los componentes actuales del proyecto.

No implementes formularios propios de tarjeta ni utilices Stripe Elements.

## 7. Implementar los webhooks de Stripe

Crea un endpoint:

`POST /api/billing/webhook/`

Este endpoint debe recibir y procesar los eventos enviados por Stripe.

Implementa como mínimo los siguientes eventos para suscripciones:

- `checkout.session.completed`
- `invoice.paid`
- `invoice.payment_failed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`

Si se permiten métodos de pago asíncronos, gestiona también sus eventos de confirmación y fallo.

Requisitos:

- Verificar la firma del webhook utilizando `STRIPE_WEBHOOK_SECRET`.
- Utilizar el cuerpo original de la petición para verificar la firma.
- Aplicar idempotencia para evitar procesar dos veces el mismo evento.
- Gestionar eventos recibidos fuera de orden.
- Utilizar transacciones de base de datos cuando corresponda.
- Registrar los errores sin exponer información sensible.
- Permitir que Stripe reintente los eventos que no se hayan procesado correctamente.

Nunca activar una suscripción únicamente porque el usuario haya sido redirigido a la página de éxito.

## 8. Gestionar el acceso a funcionalidades premium

Integra el estado de la suscripción con el sistema de permisos existente.

- Conceder acceso cuando la suscripción cumpla las condiciones establecidas.
- Gestionar correctamente los periodos de prueba, si existen.
- Mantener el acceso hasta finalizar el periodo contratado cuando exista una cancelación programada.
- Gestionar los pagos fallidos según la política de acceso de la aplicación.
- Revocar el acceso cuando corresponda.

Las comprobaciones de permisos deben realizarse también en el backend, no únicamente en el frontend.

## 9. Implementar Stripe Customer Portal

Crea un endpoint autenticado:

`POST /api/billing/portal/`

Debe generar una sesión de Stripe Customer Portal para el cliente asociado al usuario y devolver la URL correspondiente.

Añade un botón de «Gestionar suscripción» en el apartado de configuración o cuenta del usuario.

Desde el portal de Stripe, según su configuración, el usuario podrá:

- Cancelar su suscripción.
- Cambiar de plan.
- Actualizar su método de pago.
- Consultar y descargar facturas.
- Modificar sus datos de facturación.

No quiero desarrollar estas funcionalidades manualmente si Stripe ya las proporciona.

## 10. Páginas de éxito y cancelación

Crea o adapta las siguientes páginas del frontend:

- `/payment/success`
- `/payment/cancel`

La página de éxito debe consultar el estado real de la suscripción en el backend y mostrar un estado pendiente si todavía no se ha procesado el pago.

La página de cancelación debe permitir volver a intentar el pago o regresar a los planes disponibles.

## 11. Endpoint de estado de suscripción

Implementa un endpoint autenticado:

`GET /api/billing/subscription/`

Debe devolver la información necesaria para que el frontend pueda mostrar:

- Plan actual.
- Estado de la suscripción.
- Fecha de renovación o finalización.
- Cancelación programada.
- Disponibilidad de funcionalidades premium.

Adapta el formato de respuesta a las convenciones existentes del proyecto.

## 12. Pruebas

Implementa pruebas automatizadas para verificar:

- Creación de sesiones de Checkout.
- Validación de planes.
- Autenticación y permisos.
- Prevención de suscripciones duplicadas.
- Verificación de firmas de webhooks.
- Procesamiento de eventos duplicados.
- Activación y cancelación de suscripciones.
- Fallos de pago.
- Acceso a funcionalidades premium.
- Creación de sesiones de Customer Portal.

Utiliza mocks de Stripe en las pruebas unitarias y documenta las pruebas de integración en modo test.

## 13. Documentación

Genera un archivo `STRIPE_SETUP.md` explicando:

- Cómo configurar Stripe Dashboard.
- Cómo crear productos y precios.
- Qué variables de entorno configurar.
- Cómo ejecutar las migraciones.
- Cómo instalar y utilizar Stripe CLI.
- Cómo probar los webhooks localmente.
- Cómo configurar Customer Portal.
- Cómo probar pagos.
- Cómo pasar del entorno de pruebas a producción.

## Instrucciones finales

- Respeta la arquitectura y las convenciones del proyecto.
- Utiliza el SDK oficial de Stripe.
- No introduzcas dependencias innecesarias.
- No dupliques modelos ni funcionalidades existentes.
- Prioriza seguridad, mantenibilidad e idempotencia.
- Antes de implementar, presenta un plan de trabajo basado en el código existente.
- Identifica las decisiones de negocio que necesiten mi confirmación.
- Implementa los cambios por fases.
- Ejecuta las pruebas y comprobaciones disponibles.
- No realices cobros reales ni despliegues en producción.

Al finalizar, proporciona un resumen de los archivos creados y modificados, las pruebas realizadas y los pasos que debo completar manualmente en Stripe Dashboard.