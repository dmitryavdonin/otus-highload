#!/usr/bin/env python3
"""
Упрощенный скрипт для проверки корректности сохранения сообщений
через статистику API и прямые запросы к базе данных
"""

import asyncio
import aiohttp
import json
import os
import subprocess
from typing import Dict, Any

API_URL = "http://localhost:9000"

class SimpleMessageVerifier:
    def __init__(self, api_url: str = API_URL):
        self.api_url = api_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_service_health(self) -> bool:
        """Проверка доступности сервиса"""
        try:
            async with self.session.get(f"{self.api_url}/docs") as response:
                return response.status == 200
        except Exception as e:
            print(f"❌ Сервис недоступен: {e}")
            return False
    
    def check_postgresql_messages(self) -> Dict[str, Any]:
        """Проверка сообщений в PostgreSQL через прямой запрос к БД"""
        try:
            # Подсчет сообщений в PostgreSQL
            result = subprocess.run([
                "docker", "exec", "citus-coordinator", 
                "psql", "-U", "postgres", "-d", "social_network", 
                "-t", "-c", "SELECT COUNT(*) FROM dialog_messages;"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                count = int(result.stdout.strip())
                
                # Получаем примеры сообщений
                sample_result = subprocess.run([
                    "docker", "exec", "citus-coordinator", 
                    "psql", "-U", "postgres", "-d", "social_network", 
                    "-t", "-c", "SELECT from_user_id, to_user_id, text, created_at FROM dialog_messages LIMIT 5;"
                ], capture_output=True, text=True, timeout=10)
                
                samples = []
                if sample_result.returncode == 0:
                    lines = sample_result.stdout.strip().split('\n')
                    for line in lines:
                        if line.strip():
                            parts = line.split('|')
                            if len(parts) >= 4:
                                samples.append({
                                    "from_user_id": parts[0].strip(),
                                    "to_user_id": parts[1].strip(),
                                    "text": parts[2].strip(),
                                    "created_at": parts[3].strip()
                                })
                
                return {
                    "status": "success",
                    "backend": "PostgreSQL",
                    "total_messages": count,
                    "sample_messages": samples
                }
            else:
                return {
                    "status": "error",
                    "backend": "PostgreSQL",
                    "error": result.stderr
                }
        except Exception as e:
            return {
                "status": "error",
                "backend": "PostgreSQL",
                "error": str(e)
            }
    
    def check_redis_messages(self) -> Dict[str, Any]:
        """Проверка сообщений в Redis"""
        try:
            # Подсчет ключей диалогов в Redis
            result = subprocess.run([
                "docker", "exec", "otus-highload-redis-1", 
                "redis-cli", "KEYS", "dialog:*"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                keys = [k.strip() for k in result.stdout.strip().split('\n') if k.strip()]
                
                total_messages = 0
                sample_messages = []
                
                # Проверяем несколько ключей для подсчета сообщений
                for key in keys[:10]:  # Проверяем первые 10 ключей
                    try:
                        count_result = subprocess.run([
                            "docker", "exec", "otus-highload-redis-1", 
                            "redis-cli", "LLEN", key
                        ], capture_output=True, text=True, timeout=5)
                        
                        if count_result.returncode == 0:
                            count = int(count_result.stdout.strip())
                            total_messages += count
                            
                            # Получаем пример сообщения
                            if count > 0 and len(sample_messages) < 5:
                                sample_result = subprocess.run([
                                    "docker", "exec", "otus-highload-redis-1", 
                                    "redis-cli", "LINDEX", key, "0"
                                ], capture_output=True, text=True, timeout=5)
                                
                                if sample_result.returncode == 0:
                                    try:
                                        message_data = json.loads(sample_result.stdout.strip())
                                        sample_messages.append({
                                            "dialog_key": key,
                                            "message": message_data
                                        })
                                    except:
                                        pass
                    except:
                        continue
                
                return {
                    "status": "success",
                    "backend": "Redis",
                    "total_dialog_keys": len(keys),
                    "estimated_messages": total_messages,
                    "sample_messages": sample_messages
                }
            else:
                return {
                    "status": "error",
                    "backend": "Redis",
                    "error": result.stderr
                }
        except Exception as e:
            return {
                "status": "error",
                "backend": "Redis",
                "error": str(e)
            }
    
    async def run_verification(self) -> None:
        """Запуск проверки"""
        print("🚀 Запуск проверки корректности сохранения сообщений")
        print("=" * 60)
        
        # Проверяем доступность сервиса
        if not await self.check_service_health():
            print("❌ Сервис недоступен")
            return
        
        print("✅ Сервис доступен")
        
        results = {}
        
        # Проверяем PostgreSQL
        print("\n📊 Проверка PostgreSQL...")
        results["postgresql"] = self.check_postgresql_messages()
        
        # Проверяем Redis
        print("\n📊 Проверка Redis...")
        results["redis"] = self.check_redis_messages()
        
        # Выводим отчет
        self.print_verification_report(results)
        
        # Сохраняем результаты
        self.save_verification_results(results)
    
    def print_verification_report(self, results: Dict[str, Any]) -> None:
        """Вывод отчета проверки"""
        print("\n" + "=" * 60)
        print("📋 ОТЧЕТ ПРОВЕРКИ СООБЩЕНИЙ")
        print("=" * 60)
        
        for backend_key, result in results.items():
            backend_name = result.get("backend", backend_key)
            status = result.get("status", "unknown")
            
            print(f"\n🔹 {backend_name}:")
            if status == "success":
                print(f"   ✅ Статус: Успешно")
                
                if backend_key == "postgresql":
                    print(f"   📝 Всего сообщений: {result.get('total_messages', 0)}")
                    samples = result.get('sample_messages', [])
                    if samples:
                        print(f"   📄 Примеры сообщений:")
                        for i, sample in enumerate(samples[:3]):
                            print(f"      {i+1}. От: {sample['from_user_id'][:8]}... → К: {sample['to_user_id'][:8]}...")
                            print(f"         Текст: {sample['text'][:50]}...")
                
                elif backend_key == "redis":
                    print(f"   🔑 Ключей диалогов: {result.get('total_dialog_keys', 0)}")
                    print(f"   📝 Примерное количество сообщений: {result.get('estimated_messages', 0)}")
                    samples = result.get('sample_messages', [])
                    if samples:
                        print(f"   📄 Примеры сообщений:")
                        for i, sample in enumerate(samples[:3]):
                            msg = sample.get('message', {})
                            print(f"      {i+1}. Ключ: {sample['dialog_key']}")
                            print(f"         Текст: {msg.get('text', 'N/A')[:50]}...")
            else:
                print(f"   ❌ Статус: Ошибка")
                print(f"   📄 Ошибка: {result.get('error', 'Неизвестная ошибка')}")
        
        # Сравнение
        if "postgresql" in results and "redis" in results:
            pg_result = results["postgresql"]
            redis_result = results["redis"]
            
            if (pg_result.get("status") == "success" and 
                redis_result.get("status") == "success"):
                
                pg_count = pg_result.get('total_messages', 0)
                redis_count = redis_result.get('estimated_messages', 0)
                
                print(f"\n🔍 СРАВНЕНИЕ:")
                print(f"   📊 PostgreSQL: {pg_count} сообщений")
                print(f"   📊 Redis: ~{redis_count} сообщений")
                
                if pg_count > 0 and redis_count > 0:
                    if abs(pg_count - redis_count) <= pg_count * 0.1:  # 10% погрешность
                        print(f"   ✅ Количество сообщений примерно совпадает")
                    else:
                        print(f"   ⚠️  Обнаружены значительные различия в количестве сообщений")
                elif pg_count == 0 and redis_count == 0:
                    print(f"   ⚠️  В обеих системах нет сообщений")
                else:
                    print(f"   ❌ Одна из систем не содержит сообщений")
    
    def save_verification_results(self, results: Dict[str, Any]) -> None:
        """Сохранение результатов"""
        os.makedirs("lesson-07", exist_ok=True)
        
        with open("lesson-07/message_verification_simple.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Результаты сохранены в: lesson-07/message_verification_simple.json")

async def main():
    """Главная функция"""
    async with SimpleMessageVerifier() as verifier:
        await verifier.run_verification()

if __name__ == "__main__":
    asyncio.run(main()) 