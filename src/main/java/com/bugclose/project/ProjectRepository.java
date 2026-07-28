package com.bugclose.project;

import org.springframework.data.jpa.repository.JpaRepository;

public interface ProjectRepository extends JpaRepository<Project, Long> {

    boolean existsByName(String name);

    boolean existsByNameAndIdNot(String name, Long id);

    boolean existsByCode(String code);

    boolean existsByCodeAndIdNot(String code, Long id);
}
