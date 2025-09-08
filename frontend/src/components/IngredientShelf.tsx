"use client";
import Image from "next/image";
import { Lock } from "lucide-react";

type Ingredient = { id: string; name: string; src: string; earned: boolean };

export default function IngredientShelf({ items }: { items: Ingredient[] }) {
  return (
    <div className="grid grid-cols-4 gap-3">
      {items.map((it) => (
        <div key={it.id} className="relative rounded-xl border p-2 bg-white">
          <div className="aspect-square relative">
            <Image
              src={it.src}
              alt={it.name}
              fill
              sizes="96px"
              className={`${it.earned ? "" : "opacity-30"}`}
            />
          </div>
          <div className="mt-2 text-center text-xs font-medium">{it.name}</div>
          {!it.earned && (
            <div className="absolute top-2 right-2 bg-neutral-900/70 text-white rounded-full p-1">
              <Lock className="w-3 h-3" />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
