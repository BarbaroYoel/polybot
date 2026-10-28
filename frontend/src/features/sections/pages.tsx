import { SectionPage } from "./SectionPage";

export function SettingsPage() {
  return (
    <SectionPage
      title="Configuración"
      description="Preferencias del tutor, de la voz y de privacidad. Nada de esto cambia todavía el comportamiento del producto."
      phase="Vista base · F1"
      items={[
        "Tutor: correcciones inmediatas o al final, formalidad, ritmo y dificultad.",
        "Voz: voz disponible, velocidad de reproducción y subtítulos.",
        "Privacidad: historial, audio y permisos de micrófono.",
        "Generales: idioma de la interfaz, notificaciones y tema (más adelante).",
      ]}
    />
  );
}

export function NotFoundPage() {
  return (
    <SectionPage
      title="Esa pantalla no existe"
      description="La ruta que pediste no está en la aplicación."
      phase="404"
      items={["Volvé a Conversaciones desde la barra lateral."]}
    />
  );
}
