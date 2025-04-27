import asyncio
import yaml
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DOCKER_COMPOSE_FILE = "./docker-compose-replication.yml"

async def clear_all_tables(session: AsyncSession):
    # Use single TRUNCATE with CASCADE to clear all tables with FK dependencies
    await session.execute(text('''TRUNCATE TABLE friends, posts, auth_tokens, users CASCADE;'''))
    await session.commit()
    print("All tables cleared successfully.")


def load_db_config_from_docker_compose(file_path: str):
    with open(file_path, 'r') as f:
        compose = yaml.safe_load(f)

    services = compose.get('services', {})
    db_master = services.get('db-master', {})
    environment = db_master.get('environment', [])

    # environment can be list or dict
    env_dict = {}
    if isinstance(environment, list):
        for item in environment:
            if '=' in item:
                key, value = item.split('=', 1)
                env_dict[key] = value
    elif isinstance(environment, dict):
        env_dict = environment

    return {
        'DB_HOST': env_dict.get('POSTGRES_HOST', 'localhost'),
        'DB_PORT': env_dict.get('POSTGRES_PORT', '5432'),
        'DB_NAME': env_dict.get('POSTGRES_DB', 'social_network'),
        'DB_USER': env_dict.get('POSTGRES_USER', 'postgres'),
        'DB_PASSWORD': env_dict.get('POSTGRES_PASSWORD', 'postgres'),
    }


async def main():
    config = load_db_config_from_docker_compose(DOCKER_COMPOSE_FILE)

    # Compose the database URL
    db_url = f"postgresql+asyncpg://{config['DB_USER']}:{config['DB_PASSWORD']}@localhost:{config['DB_PORT']}/{config['DB_NAME']}"

    engine = create_async_engine(db_url, echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as session:
        await clear_all_tables(session)


if __name__ == '__main__':
    asyncio.run(main())
