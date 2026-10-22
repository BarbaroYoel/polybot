import { SectionPage } from "./SectionPage";

export function LessonsPage() {
  return (
    <SectionPage
      title="Lecciones"
      description="El siguiente paso de aprendizaje del idioma activo: unidades cortas con práctica y feedback del tutor."
      phase="Vista base · F1"
      items={[
        "Continuar aprendiendo: la lección siguiente en una tarjeta destacada.",
        "Unidades de vocabulario, gramática, pronunciación, escucha y práctica situacional.",
        "Duración estimada, dificultad y estado de cada lección.",
        "Al terminar: resultado, errores relevantes, vocabulario nuevo y próxima recomendación.",
      ]}
    />
  );
}

export function PlansPage() {
  return (
    <SectionPage
      title="Planes de estudio"
      description="Un objetivo transformado en una ruta de aprendizaje con frecuencia, tiempo diario y sesiones."
      phase="Vista base · F1"
      items={[
        "Objetivo explícito, por ejemplo «Pasar de A1 a B1 en francés».",
        "Frecuencia de estudio y tiempo diario configurables.",
        "Cronograma por semanas y sesiones pendientes, en curso o completadas.",
        "«Continuar plan» como acción primaria y «Ajustar plan» como secundaria.",
      ]}
    />
  );
}

export function TranslatePage() {
  return (
    <SectionPage
      title="Traducción en tiempo real"
      description="Dos flujos separados: traducir texto e interpretar voz, sin mezclarlos con una lección."
      phase="Vista base · F1"
      items={[
        "Traducir texto: idioma de origen y destino, entrada, traducción, copiar y reproducir.",
        "Intérprete de voz: iniciar y detener escucha, señal clara de micrófono activo.",
        "Historial de fragmentos originales y traducidos, ordenados en el tiempo.",
        "Estados de permiso, conexión, escucha, procesamiento y error.",
      ]}
    />
  );
}

export function ProgressPage() {
  return (
    <SectionPage
      title="Progreso"
      description="Feedback útil del idioma activo sin convertirse en un dashboard recargado."
      phase="Vista base · F1"
      items={[
        "Nivel, sesiones completadas, tiempo practicado y meta semanal.",
        "Evolución por destreza: lectura, escucha, conversación, escritura y vocabulario.",
        "Errores frecuentes y elementos por repasar.",
        "Historial de prácticas y lecciones, con criterios trazables para el nivel.",
      ]}
    />
  );
}

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
