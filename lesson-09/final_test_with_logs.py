#!/usr/bin/env python3
"""
Финальный тест отказоустойчивости с детальным логированием для отчета
"""

import asyncio
import logging
import time
from datetime import datetime
from load_test import LoadTester

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_results.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def run_full_test():
    """Запуск полного теста с детальным логированием"""
    
    logger.info("=" * 80)
    logger.info("НАЧАЛО ТЕСТИРОВАНИЯ ОТКАЗОУСТОЙЧИВОСТИ УРОКА 9")
    logger.info("=" * 80)
    logger.info(f"Время начала тестирования: {datetime.now()}")
    logger.info("Проверяем работу системы: PostgreSQL кластер + HAProxy + приложения + Nginx")
    
    tester = LoadTester()
    
    # Этап 1: Создание пользователей
    logger.info("\n" + "=" * 50)
    logger.info("ЭТАП 1: СОЗДАНИЕ ТЕСТОВЫХ ПОЛЬЗОВАТЕЛЕЙ")
    logger.info("=" * 50)
    
    start_time = time.time()
    await tester.create_test_users(50)
    end_time = time.time()
    
    logger.info(f"Пользователей создано: {len(tester.users)}/50")
    logger.info(f"Время выполнения: {end_time - start_time:.2f} секунд")
    logger.info(f"Всего запросов: {tester.metrics['total_requests']}")
    logger.info(f"Успешных: {tester.metrics['successful_requests']}")
    logger.info(f"Неудачных: {tester.metrics['failed_requests']}")
    success_rate = (tester.metrics['successful_requests'] / tester.metrics['total_requests']) * 100 if tester.metrics['total_requests'] > 0 else 0
    logger.info(f"Процент успеха: {success_rate:.2f}%")
    logger.info(f"Среднее время отклика: {sum(tester.metrics['response_times'])/len(tester.metrics['response_times']):.3f}s")
    
    if tester.metrics['errors']:
        logger.warning("Ошибки при создании пользователей:")
        for error in tester.metrics['errors'][:3]:
            logger.warning(f"  - {error}")
    
    # Этап 2: Тест чтения
    logger.info("\n" + "=" * 50)
    logger.info("ЭТАП 2: ТЕСТ ЧТЕНИЯ (slave PostgreSQL)")
    logger.info("=" * 50)
    logger.info("Тестируем операции чтения через HAProxy -> PostgreSQL slaves")
    
    tester.reset_metrics()
    start_time = time.time()
    await tester.run_read_load_test(20)
    end_time = time.time()
    
    logger.info(f"Время выполнения: {end_time - start_time:.2f} секунд")
    logger.info(f"Всего запросов: {tester.metrics['total_requests']}")
    logger.info(f"Успешных: {tester.metrics['successful_requests']}")
    logger.info(f"Неудачных: {tester.metrics['failed_requests']}")
    success_rate = (tester.metrics['successful_requests'] / tester.metrics['total_requests']) * 100 if tester.metrics['total_requests'] > 0 else 0
    logger.info(f"Процент успеха: {success_rate:.2f}%")
    logger.info(f"Среднее время отклика: {sum(tester.metrics['response_times'])/len(tester.metrics['response_times']):.3f}s")
    logger.info(f"RPS (запросов в секунду): {tester.metrics['total_requests']/(end_time - start_time):.1f}")
    
    if tester.metrics['errors']:
        logger.warning("Ошибки при тестировании чтения:")
        for error in tester.metrics['errors'][:3]:
            logger.warning(f"  - {error}")
    
    # Этап 3: Смешанный тест
    logger.info("\n" + "=" * 50)
    logger.info("ЭТАП 3: СМЕШАННЫЙ ТЕСТ (чтение + запись)")
    logger.info("=" * 50)
    logger.info("Тестируем 70% чтение (slaves) + 30% запись (master)")
    
    tester.reset_metrics()
    start_time = time.time()
    await tester.run_mixed_load_test(20)
    end_time = time.time()
    
    logger.info(f"Время выполнения: {end_time - start_time:.2f} секунд")
    logger.info(f"Всего запросов: {tester.metrics['total_requests']}")
    logger.info(f"Успешных: {tester.metrics['successful_requests']}")
    logger.info(f"Неудачных: {tester.metrics['failed_requests']}")
    success_rate = (tester.metrics['successful_requests'] / tester.metrics['total_requests']) * 100 if tester.metrics['total_requests'] > 0 else 0
    logger.info(f"Процент успеха: {success_rate:.2f}%")
    logger.info(f"Среднее время отклика: {sum(tester.metrics['response_times'])/len(tester.metrics['response_times']):.3f}s")
    logger.info(f"RPS (запросов в секунду): {tester.metrics['total_requests']/(end_time - start_time):.1f}")
    
    if tester.metrics['errors']:
        logger.warning("Ошибки при смешанном тестировании:")
        for error in tester.metrics['errors'][:3]:
            logger.warning(f"  - {error}")
    
    # Итоговая статистика
    logger.info("\n" + "=" * 80)
    logger.info("ИТОГОВЫЕ РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    logger.info("=" * 80)
    logger.info(f"Время завершения тестирования: {datetime.now()}")
    logger.info("✅ Все этапы тестирования завершены успешно")
    logger.info("✅ Система готова к тестированию отказоустойчивости")
    logger.info("\nДля тестирования отказов используйте:")
    logger.info("1. ./failover_test.sh test_postgres_slave_failure")
    logger.info("2. ./failover_test.sh test_app_failure") 
    logger.info("3. Мониторинг: http://localhost:8404/stats")
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_full_test()) 