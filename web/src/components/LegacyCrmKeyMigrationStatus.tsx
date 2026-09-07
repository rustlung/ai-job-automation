interface LegacyCrmKeyMigrationStatusProps {
  matches?: number;
}

function legacyCrmKeyMatches(matches: unknown): number {
  return typeof matches === "number" && Number.isInteger(matches) && matches >= 0 ? matches : 0;
}

export function LegacyCrmKeyMigrationStatus({ matches }: LegacyCrmKeyMigrationStatusProps) {
  const count = legacyCrmKeyMatches(matches);

  return (
    <section className="border border-line bg-white p-5">
      <h2 className="text-base font-semibold">Миграция старых CRM-ключей</h2>
      <p className="mt-2 text-sm text-zinc-700">
        {count} {count === 1 ? "совпадение" : "совпадений"} в этом запуске
      </p>
      <p className="mt-1 text-sm text-zinc-500">Временная диагностика lazy-миграции строк к business CRM key.</p>
    </section>
  );
}
