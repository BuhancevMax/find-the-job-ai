using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace BlazorApp1.Migrations
{
    /// <inheritdoc />
    public partial class InitialDb : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "Vacancies",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    Title = table.Column<string>(type: "TEXT", nullable: false),
                    Company = table.Column<string>(type: "TEXT", nullable: false),
                    SalaryString = table.Column<string>(type: "TEXT", nullable: false),
                    Url = table.Column<string>(type: "TEXT", nullable: false),
                    PublishedDate = table.Column<DateTime>(type: "TEXT", nullable: false),
                    RequiredExperience = table.Column<string>(type: "TEXT", nullable: false),
                    TechStack = table.Column<string>(type: "TEXT", nullable: false),
                    AiSummary = table.Column<string>(type: "TEXT", nullable: false),
                    AiMatchScore = table.Column<int>(type: "INTEGER", nullable: false),
                    ParsedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsSaved = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Vacancies", x => x.Id);
                });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "Vacancies");
        }
    }
}
