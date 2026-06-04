// Derived from pingdotgg/t3code apps/web/src/lib/lruCache.ts (MIT).
interface CacheEntry<T> {
  value: T;
  approximateSize: number;
}

export class LRUCache<T> {
  private cache = new Map<string, CacheEntry<T>>();
  private totalSize = 0;

  constructor(
    private readonly maxEntries: number,
    private readonly maxMemoryBytes: number,
  ) {}

  get(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) return null;
    this.cache.delete(key);
    this.cache.set(key, entry);
    return entry.value;
  }

  set(key: string, value: T, approximateSize: number): void {
    if (approximateSize > this.maxMemoryBytes) return;
    const existing = this.cache.get(key);
    if (existing) {
      this.totalSize -= existing.approximateSize;
      this.cache.delete(key);
    }
    while (
      (this.cache.size >= this.maxEntries || this.totalSize + approximateSize > this.maxMemoryBytes) &&
      this.cache.size > 0
    ) {
      const oldest = this.cache.keys().next().value;
      if (oldest === undefined) break;
      const entry = this.cache.get(oldest);
      if (entry) this.totalSize -= entry.approximateSize;
      this.cache.delete(oldest);
    }
    this.cache.set(key, { value, approximateSize });
    this.totalSize += approximateSize;
  }
}
