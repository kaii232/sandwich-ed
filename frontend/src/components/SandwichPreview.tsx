"use client";
import Image from "next/image";

type Ingredient = {
  id: string;
  name: string;
  src: string;
  earned: boolean;
  z: number;
};

export default function SandwichPreview({ stack }: { stack: Ingredient[] }) {
  // Render bottom → top using z for layering
  const layers = [...stack].sort((a, b) => a.z - b.z);
  return (
    <div className="relative h-56 w-full flex items-end justify-center overflow-visible">
      <div className="relative w-56">
        {layers.map((layer) => (
          <div
            key={layer.id}
            className={`absolute inset-x-0 transition-all duration-500 ease-out
              ${
                layer.earned
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-6"
              }`}
            style={{ zIndex: layer.z, bottom: `${layer.z * 10}px` }}
          >
            <Image
              src={layer.src}
              alt={layer.name}
              width={224}
              height={64}
              priority
            />
          </div>
        ))}
      </div>
    </div>
  );
}
